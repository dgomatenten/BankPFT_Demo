"""Data file management service — fixed-length file import and export.

Import flow:
  Inbox folder  →  parse fixed-length fields per format_config  →  insert rows into target table

Export flow:
  Source table  →  apply filter_json + field transforms  →  write fixed-length file to outbox

Transform expressions are evaluated in a restricted sandbox that permits only basic
arithmetic and string operations. No builtins beyond float/int/str/round/abs/len
are accessible, preventing arbitrary code execution.
"""

import csv
import os
import json
import uuid
import ast
import math
from datetime import date, datetime
from typing import Any

from app.models import db
from app.models.datafile import DataFileBatch
from app.models.staging import StgInstData, StgGlData, ProcInstData, ProcGlData
from app.models.allocation import RefStaticAllocation, FctMgmtLedger, FctMgmtInstrument

# ── Config ──────────────────────────────────────────────────────────────────
_CFG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "datafile_config.json")
with open(_CFG_PATH) as _f:
    DATAFILE_CONFIG = json.load(_f)

# ── Load per-file import/export rules from app/config/datafile/*.json ────────
_RULES_DIR = os.path.join(os.path.dirname(__file__), "..", "config", "datafile")
DATAFILE_CONFIG.setdefault("formats", [])
DATAFILE_CONFIG.setdefault("exports", [])

for _rule_file in sorted(os.listdir(_RULES_DIR)) if os.path.isdir(_RULES_DIR) else []:
    if not _rule_file.endswith(".json"):
        continue
    with open(os.path.join(_RULES_DIR, _rule_file)) as _rf:
        _rule = json.load(_rf)
    _op = _rule.get("operation", "").lower()
    if _op == "import":
        DATAFILE_CONFIG["formats"].append(_rule)
    elif _op == "export":
        DATAFILE_CONFIG["exports"].append(_rule)
    # Files without an 'operation' key are silently skipped (e.g. lookup tables)

INBOX_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "instance",
    DATAFILE_CONFIG.get("inbox_folder", "datafile_inbox"),
)
OUTBOX_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "instance",
    DATAFILE_CONFIG.get("outbox_folder", "datafile_outbox"),
)

# ── Model registry ───────────────────────────────────────────────────────────
_TABLE_MODELS = {
    "stg_inst_data":     StgInstData,
    "stg_gl_data":       StgGlData,
    "proc_inst_data":    ProcInstData,
    "proc_gl_data":      ProcGlData,
    "ref_static_allocation": RefStaticAllocation,
    "fct_mgmt_ledger":   FctMgmtLedger,
    "fct_mgmt_instrument": FctMgmtInstrument,
}

# ── Safe expression evaluator ────────────────────────────────────────────────

def _nvl(v: Any, default: Any = "") -> Any:
    """Return v if non-None and non-empty, otherwise default (like SQL NVL/COALESCE)."""
    return default if (v is None or str(v).strip() == "") else v


def _coalesce(*args: Any) -> Any:
    """Return the first argument that is non-None and non-empty."""
    for a in args:
        if a is not None and str(a).strip() != "":
            return a
    return None


def _substr(v: Any, start: int, length: int | None = None) -> str:
    """0-based substring. substr(value, 2, 5) → chars at positions 2..6."""
    s = str(v)
    return s[start:start + length] if length is not None else s[start:]


def _to_int(v: Any, default: int = 0) -> int:
    """Safe integer conversion; returns default on error."""
    try:
        return int(float(str(v).strip()))
    except (ValueError, TypeError):
        return default


def _to_float(v: Any, default: float = 0.0) -> float:
    """Safe float conversion; returns default on error."""
    try:
        return float(str(v).strip())
    except (ValueError, TypeError):
        return default


_SAFE_NAMES: dict[str, Any] = {
    # Builtins
    "float": float, "int": int, "str": str,
    "round": round, "abs": abs, "len": len,
    "bool": bool,
    # Math module
    "math": math,
    # String helpers — use as functions: upper(value), left(value, 3), etc.
    "upper":      lambda v: str(v).upper(),
    "lower":      lambda v: str(v).lower(),
    "trim":       lambda v: str(v).strip(),
    "ltrim":      lambda v: str(v).lstrip(),
    "rtrim":      lambda v: str(v).rstrip(),
    "left":       lambda v, n: str(v)[:n],
    "right":      lambda v, n: str(v)[-n:] if n else "",
    "substr":     _substr,
    "lpad":       lambda v, width, ch=" ": str(v).rjust(int(width), str(ch)),
    "rpad":       lambda v, width, ch=" ": str(v).ljust(int(width), str(ch)),
    "replace":    lambda v, old, new: str(v).replace(str(old), str(new)),
    "concat":     lambda *args: "".join(str(a) for a in args),
    "startswith": lambda v, prefix: str(v).startswith(str(prefix)),
    "endswith":   lambda v, suffix: str(v).endswith(str(suffix)),
    "contains":   lambda v, sub: str(sub) in str(v),
    # Null / default helpers
    "nvl":        _nvl,
    "coalesce":   _coalesce,
    "iif":        lambda cond, true_val, false_val: true_val if cond else false_val,
    # Safe type conversions
    "to_int":     _to_int,
    "to_float":   _to_float,
}

_ALLOWED_NODE_TYPES = (
    # Expressions
    ast.Expression, ast.Constant, ast.Name, ast.Attribute,
    # Operators
    ast.BinOp, ast.UnaryOp,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow, ast.FloorDiv,
    ast.USub, ast.UAdd,
    # Comparisons and boolean logic (for ternary / case expressions)
    ast.IfExp, ast.Compare, ast.BoolOp,
    ast.And, ast.Or, ast.Not,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    ast.In, ast.NotIn,
    # Subscript / slice (for value[0:5] substring)
    ast.Subscript, ast.Slice,
    # Collections (for `value in ['A', 'B']` comparisons)
    ast.List, ast.Tuple,
    # Calls
    ast.Call, ast.keyword,
    # Context
    ast.Load,
)


def _safe_eval(expr: str, value: Any) -> Any:
    """Evaluate a transform expression with ``value`` as the only input variable.

    Supported constructs (examples in datafile_config.json):
      Arithmetic       : float(value) / 100.0
      Ternary / case   : "DEBIT" if float(value) > 0 else "CREDIT"
      String functions : upper(value), left(value, 3), substr(value, 2, 4)
      Slicing          : value[0:5]
      Padding          : lpad(value, 10, '0')
      Replace          : replace(value, '-', '')
      Concat           : concat(left(value, 3), '-', right(value, 4))
      Null default     : nvl(value, 'UNKNOWN')
      Safe conversion  : to_float(value) * 1.1
      Boolean in list  : "Y" if value in ["A","B"] else "N"

    All other AST node types are rejected to prevent code injection.
    Attribute access to names starting with '_' is also blocked.
    """
    tree = ast.parse(expr, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODE_TYPES):
            raise ValueError(f"Unsafe expression node '{type(node).__name__}' in: {expr!r}")
        if isinstance(node, ast.Name) and node.id not in ("value", *_SAFE_NAMES):
            raise ValueError(f"Disallowed name '{node.id}' in: {expr!r}")
        # Block dunder / private attribute access (e.g. value.__class__)
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            raise ValueError(f"Attribute access to '{node.attr}' is not permitted in: {expr!r}")
    return eval(compile(tree, "<expr>", "eval"), {"__builtins__": {}}, {**_SAFE_NAMES, "value": value})  # noqa: S307


# ── Helpers ──────────────────────────────────────────────────────────────────
def _coerce(raw: str, field_cfg: dict) -> Any:
    """Strip, transform, and coerce a raw string value according to field config."""
    val = raw.strip()
    t = field_cfg.get("type", "string")
    transform = field_cfg.get("transform")

    if t == "date":
        fmt = field_cfg.get("date_format", "%Y-%m-%d")
        return datetime.strptime(val, fmt).date()

    if t == "float":
        num = float(val) if val else 0.0
        return _safe_eval(transform, num) if transform else num

    if t == "int":
        num = int(val) if val else 0
        return _safe_eval(transform, num) if transform else num

    # string
    result = _safe_eval(transform, val) if transform else val
    return str(result)


def _apply_export_filters(rows: list, filter_cfg: dict) -> list:
    """Apply filter_json conditions to a list of SQLAlchemy model instances."""
    conditions = filter_cfg.get("conditions", [])
    if not conditions:
        return rows
    logic = filter_cfg.get("logic", "AND")

    def _matches(row) -> bool:
        results = []
        for c in conditions:
            col, op, val = c.get("field"), c.get("operator"), str(c.get("value", ""))
            attr = str(getattr(row, col, "")) if col else ""
            if op == "eq":
                results.append(attr == val)
            elif op == "neq":
                results.append(attr != val)
            elif op == "in":
                results.append(attr in {v.strip() for v in val.split(",")})
            elif op == "not_in":
                results.append(attr not in {v.strip() for v in val.split(",")})
            elif op == "contains":
                results.append(val.lower() in attr.lower())
            elif op == "gt":
                results.append(float(attr) > float(val))
            elif op == "gte":
                results.append(float(attr) >= float(val))
            elif op == "lt":
                results.append(float(attr) < float(val))
            elif op == "lte":
                results.append(float(attr) <= float(val))
            else:
                results.append(True)
        return all(results) if logic == "AND" else any(results)

    return [r for r in rows if _matches(r)]


def _format_delimited_field(raw: Any, field_cfg: dict) -> str:
    """Format a single field value for delimited (CSV) export — no padding."""
    t = field_cfg.get("type", "string")
    transform = field_cfg.get("transform")
    decimals = field_cfg.get("decimals")

    if raw is None:
        return ""
    if transform:
        raw = _safe_eval(transform, raw)
    if t == "date":
        fmt = field_cfg.get("date_format", "%Y-%m-%d")
        if isinstance(raw, (date, datetime)):
            return raw.strftime(fmt)
        return str(raw)
    if t in ("float", "int"):
        if decimals is not None:
            return f"{round(float(raw), decimals):.{decimals}f}"
        return str(raw)
    return str(raw)


def _format_export_field(raw: Any, field_cfg: dict) -> str:
    """Format a single field value into a fixed-width string."""
    length = field_cfg["length"]
    t = field_cfg.get("type", "string")
    transform = field_cfg.get("transform")
    decimals = field_cfg.get("decimals")

    if raw is None:
        raw = ""

    # Apply transform expression before formatting
    if transform:
        raw = _safe_eval(transform, raw)

    if t == "date":
        fmt = field_cfg.get("date_format", "%Y-%m-%d")
        if isinstance(raw, (date, datetime)):
            text = raw.strftime(fmt)
        else:
            text = str(raw)
    elif t in ("float", "int"):
        if decimals is not None:
            text = f"{round(float(raw), decimals):.{decimals}f}"
        else:
            text = str(raw)
    else:
        text = str(raw)

    # Pad or truncate to exact field length
    if len(text) > length:
        text = text[:length]
    else:
        text = text.ljust(length)

    return text


# ── File row parsers ────────────────────────────────────────────────────────
def _parse_file_rows(filepath: str, fmt_cfg: dict):
    """Generator: yield (lineno, {field_name: raw_str}) for each data row.

    Handles both ``type: fixed_length`` (slice by start/length) and
    ``type: delimited`` (CSV/pipe/tab split with optional header-name mapping).
    """
    file_type = fmt_cfg.get("type", "fixed_length")
    skip = fmt_cfg.get("skip_header_rows", 0)
    fields = fmt_cfg["fields"]

    with open(filepath, encoding="utf-8", errors="replace", newline="") as fh:
        if file_type == "delimited":
            delimiter = fmt_cfg.get("delimiter", ",")
            quotechar = fmt_cfg.get("quotechar", '"')
            use_header = fmt_cfg.get("use_header_names", False)
            reader = csv.reader(fh, delimiter=delimiter, quotechar=quotechar)
            header_map: dict[str, int] = {}

            for lineno, row_cols in enumerate(reader, start=1):
                if lineno <= skip:
                    # If the last skipped row is the header row, capture column names
                    if use_header and lineno == skip:
                        header_map = {name.strip(): i for i, name in enumerate(row_cols)}
                    continue
                if not any(c.strip() for c in row_cols):
                    continue
                raw_vals: dict[str, str] = {}
                for field in fields:
                    # "source" overrides header lookup key; "name" is always the target key
                    header_key = field.get("source", field["name"])
                    if "column" in field:
                        col_idx = field["column"]
                    elif use_header and header_key in header_map:
                        col_idx = header_map[header_key]
                    else:
                        raw_vals[field["name"]] = ""
                        continue
                    raw_vals[field["name"]] = row_cols[col_idx] if col_idx < len(row_cols) else ""
                yield lineno, raw_vals
        else:
            # fixed_length: extract by (start-1, start-1+length)
            for lineno, line in enumerate(fh, start=1):
                if lineno <= skip:
                    continue
                raw_line = line.rstrip("\r\n")
                if not raw_line.strip():
                    continue
                raw_vals = {}
                for field in fields:
                    s = field["start"] - 1
                    e = s + field["length"]
                    raw_vals[field["name"]] = raw_line[s:e] if len(raw_line) >= e else ""
                yield lineno, raw_vals


# ── Public API ───────────────────────────────────────────────────────────────
def list_inbox_files() -> list[dict]:
    """Return metadata for every file currently in the inbox folder."""
    os.makedirs(INBOX_DIR, exist_ok=True)
    result = []
    for fname in sorted(os.listdir(INBOX_DIR)):
        fpath = os.path.join(INBOX_DIR, fname)
        if os.path.isfile(fpath):
            stat = os.stat(fpath)
            result.append({
                "filename": fname,
                "path": fpath,
                "size_bytes": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            })
    return result


def import_file(format_id: str, filename: str, run_by: str) -> DataFileBatch:
    """Parse a fixed-length file from the inbox and load rows into the target table.

    Each field is extracted by (start, length), coerced to the configured type,
    and optionally transformed via a safe arithmetic/string expression.
    """
    fmt_cfg = next((f for f in DATAFILE_CONFIG["formats"] if f["format_id"] == format_id), None)
    if not fmt_cfg:
        raise ValueError(f"Unknown format_id: {format_id!r}")

    TargetModel = _TABLE_MODELS.get(fmt_cfg["target_table"])
    if not TargetModel:
        raise ValueError(f"No model registered for table: {fmt_cfg['target_table']!r}")

    batch_id = str(uuid.uuid4())
    batch = DataFileBatch(
        id=batch_id,
        operation="IMPORT",
        format_id=format_id,
        format_name=fmt_cfg.get("name", format_id),
        filename=filename,
        target_table=fmt_cfg["target_table"],
        status="RUNNING",
        run_by=run_by,
        started_at=datetime.utcnow(),
    )
    db.session.add(batch)
    db.session.commit()

    filepath = os.path.join(INBOX_DIR, filename)
    errors: list[str] = []
    rows_loaded = 0
    skip = fmt_cfg.get("skip_header_rows", 0)
    fields = fmt_cfg["fields"]

    try:
        for lineno, raw_vals in _parse_file_rows(filepath, fmt_cfg):
            row_data: dict[str, Any] = {"datafile_batch_id": batch_id}
            row_errors: list[str] = []

            for field in fields:
                raw_val = raw_vals.get(field["name"], "")
                try:
                    row_data[field["name"]] = _coerce(raw_val, field)
                except (ValueError, KeyError) as exc:
                    row_errors.append(f"Line {lineno}, field '{field['name']}': {exc}")

            if row_errors:
                errors.extend(row_errors)
                continue

            # Replace upload_batch_id column name if target model uses it
            if hasattr(TargetModel, "upload_batch_id") and "datafile_batch_id" not in [
                c.key for c in TargetModel.__table__.columns
            ]:
                row_data["upload_batch_id"] = row_data.pop("datafile_batch_id", batch_id)
            else:
                row_data.pop("datafile_batch_id", None)

            db.session.add(TargetModel(**row_data))
            rows_loaded += 1

        batch.row_count = rows_loaded
        batch.error_count = len(errors)
        batch.errors_json = json.dumps(errors[:100]) if errors else None
        batch.status = "COMPLETED" if rows_loaded > 0 else "FAILED"
        if rows_loaded == 0:
            batch.error_message = "No rows were loaded. Check errors for details."
        batch.completed_at = datetime.utcnow()
        db.session.commit()

    except Exception as exc:
        batch.status = "FAILED"
        batch.error_message = str(exc)
        batch.completed_at = datetime.utcnow()
        db.session.commit()

    return batch


def export_data(export_id: str, run_by: str, as_of_date_str: str | None = None) -> DataFileBatch:
    """Query a source table, apply filters and transforms, write a fixed-length file.

    The output file is written to the outbox folder. All field values are
    padded/truncated to the exact configured length so the file is byte-perfect.
    """
    exp_cfg = next((e for e in DATAFILE_CONFIG["exports"] if e["export_id"] == export_id), None)
    if not exp_cfg:
        raise ValueError(f"Unknown export_id: {export_id!r}")

    SourceModel = _TABLE_MODELS.get(exp_cfg["source_table"])
    if not SourceModel:
        raise ValueError(f"No model registered for table: {exp_cfg['source_table']!r}")

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    ext = ".csv" if exp_cfg.get("format") == "delimited" else ".dat"
    out_filename = f"{export_id}_{ts}{ext}"
    batch_id = str(uuid.uuid4())
    batch = DataFileBatch(
        id=batch_id,
        operation="EXPORT",
        format_id=export_id,
        format_name=exp_cfg.get("name", export_id),
        filename=out_filename,
        target_table=exp_cfg["source_table"],
        status="RUNNING",
        run_by=run_by,
        started_at=datetime.utcnow(),
    )
    db.session.add(batch)
    db.session.commit()

    try:
        os.makedirs(OUTBOX_DIR, exist_ok=True)

        query = SourceModel.query
        # Optional as_of_date filter if the model has the column
        if as_of_date_str and hasattr(SourceModel, "as_of_date"):
            try:
                aod = datetime.strptime(as_of_date_str, "%Y-%m-%d").date()
                query = query.filter(SourceModel.as_of_date == aod)
            except ValueError:
                pass

        all_rows = query.all()

        # Apply filter_json from export config
        filter_cfg = exp_cfg.get("filter_json", {})
        filtered_rows = _apply_export_filters(all_rows, filter_cfg)

        field_defs = exp_cfg["fields"]
        export_format = exp_cfg.get("format", "fixed_length")
        include_header = exp_cfg.get("include_header", True)

        outpath = os.path.join(OUTBOX_DIR, out_filename)
        rows_written = 0

        if export_format == "delimited":
            delimiter = exp_cfg.get("delimiter", ",")
            quotechar = exp_cfg.get("quotechar", '"')
            with open(outpath, "w", encoding="utf-8", newline="") as fh:
                writer = csv.writer(fh, delimiter=delimiter, quotechar=quotechar)
                if include_header:
                    writer.writerow([fld.get("header", fld["source_col"]).strip() for fld in field_defs])
                for row in filtered_rows:
                    writer.writerow(
                        [_format_delimited_field(getattr(row, fld["source_col"], None), fld) for fld in field_defs]
                    )
                    rows_written += 1
        else:
            record_length = sum(f["length"] for f in field_defs)
            with open(outpath, "w", encoding="utf-8", newline="\n") as fh:
                # Header line
                if include_header:
                    header = "".join(
                        f["header"].ljust(f["length"])[:f["length"]]
                        for f in field_defs
                    )
                    fh.write(header + "\n")

                for row in filtered_rows:
                    parts = []
                    for fld in field_defs:
                        raw = getattr(row, fld["source_col"], None)
                        parts.append(_format_export_field(raw, fld))
                    line = "".join(parts)
                    # Ensure the record is exactly the expected length
                    if len(line) < record_length:
                        line = line.ljust(record_length)
                    fh.write(line + "\n")
                    rows_written += 1

        batch.row_count = rows_written
        batch.status = "COMPLETED"
        batch.completed_at = datetime.utcnow()
        db.session.commit()

    except Exception as exc:
        batch.status = "FAILED"
        batch.error_message = str(exc)
        batch.completed_at = datetime.utcnow()
        db.session.commit()

    return batch
