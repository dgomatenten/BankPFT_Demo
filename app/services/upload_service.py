"""Excel upload parsing and validation service — driven by upload_config.json."""

import os
import uuid
import json
from datetime import datetime
import pandas as pd
from werkzeug.utils import secure_filename
from app.models import db
from app.models.workflow import UploadBatch
from app.models.registry import MODEL_REGISTRY, DIMENSION_REGISTRY
from app.core.config_loader import load_config

# ── Load configuration ──
UPLOAD_CONFIG = load_config("upload_config")
VALIDATION_RULES_CONFIG = load_config("validation_rules")

ALLOWED_EXTENSIONS = set(UPLOAD_CONFIG["allowed_extensions"])

# Index validation rules by id for quick lookup
_VRULES = {r["id"]: r for r in VALIDATION_RULES_CONFIG["rules"]}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _read_file(filepath: str) -> pd.DataFrame:
    if filepath.endswith(".csv"):
        return pd.read_csv(filepath)
    return pd.read_excel(filepath, engine="openpyxl")


def _get_dimension_values(dim_name: str) -> set[str]:
    """Load valid values for a dimension from the database."""
    model, key_col = DIMENSION_REGISTRY[dim_name]
    return {getattr(r, key_col) for r in model.query.all()}


def validate_upload(df: pd.DataFrame, data_type: str) -> list[str]:
    """Generic config-driven validator — runs only rules listed in the data type's validation_rules."""
    type_cfg = UPLOAD_CONFIG["data_types"].get(data_type)
    if not type_cfg:
        return [f"Unknown data type: {data_type}"]

    errors = []
    max_shown = VALIDATION_RULES_CONFIG.get("max_errors_shown", 10)
    active_rule_ids = type_cfg.get("validation_rules", [])

    for rule_id in active_rule_ids:
        vrule = _VRULES.get(rule_id)
        if not vrule or not vrule.get("enabled"):
            continue

        new_errors = _run_validation_rule(rule_id, df, type_cfg, max_shown)
        errors.extend(new_errors)

        # Stop early if this rule is configured to halt on failure
        if new_errors and vrule.get("stop_on_fail"):
            break

    return errors


def _run_validation_rule(rule_id: str, df: pd.DataFrame, type_cfg: dict, max_shown: int) -> list[str]:
    """Dispatch a single validation rule by its config id."""
    errors = []

    if rule_id == "required_columns":
        for col in type_cfg["required_columns"]:
            if col not in df.columns:
                errors.append(f"Missing required column: {col}")

    elif rule_id == "null_check":
        req = [c for c in type_cfg["required_columns"] if c in df.columns]
        if req and df[req].isnull().any().any():
            null_cols = [c for c in req if df[c].isnull().any()]
            errors.append(f"Null values found in: {null_cols}")

    elif rule_id == "unique_key":
        key = type_cfg.get("unique_key")
        if key and key in df.columns and df[key].duplicated().any():
            errors.append(f"Duplicate {key} values found.")

    elif rule_id == "dimension_lookup":
        for col, dim_name in type_cfg.get("dimension_lookups", {}).items():
            if col not in df.columns:
                continue
            valid_values = _get_dimension_values(dim_name)
            bad_values = set(df[col].astype(str)) - valid_values
            if bad_values:
                errors.append(f"Unknown {col}: {sorted(bad_values)[:max_shown]}")

    elif rule_id == "ratio_sum":
        ratio_cfg = type_cfg.get("ratio_validation")
        if ratio_cfg and ratio_cfg.get("enabled"):
            group_by = ratio_cfg["group_by"]
            sum_col = ratio_cfg["sum_column"]
            expected = ratio_cfg["expected_sum"]
            tolerance = ratio_cfg["tolerance"]
            if sum_col in df.columns and all(g in df.columns for g in group_by):
                grouped = df.groupby(group_by)[sum_col].sum()
                bad_ratios = grouped[abs(grouped - expected) > tolerance]
                if not bad_ratios.empty:
                    for keys, total in bad_ratios.items():
                        label = ", ".join(f"{g}={k}" for g, k in zip(group_by, keys if isinstance(keys, tuple) else (keys,)))
                        errors.append(f"Ratio sum for {label} is {total:.4f}, expected {expected}")

    elif rule_id == "numeric_range":
        for col, bounds in type_cfg.get("numeric_ranges", {}).items():
            if col not in df.columns:
                continue
            col_data = pd.to_numeric(df[col], errors="coerce")
            if bounds.get("min") is not None:
                below = col_data[col_data < bounds["min"]]
                if not below.empty:
                    errors.append(f"{col}: {len(below)} values below minimum {bounds['min']}")
            if bounds.get("max") is not None:
                above = col_data[col_data > bounds["max"]]
                if not above.empty:
                    errors.append(f"{col}: {len(above)} values above maximum {bounds['max']}")

    return errors


def _cast_value(value, col_cfg):
    """Cast a DataFrame cell value according to column_mapping config."""
    col_type = col_cfg["type"]
    if col_type == "date":
        try:
            return pd.to_datetime(value).date()
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Cannot parse '{value}' as a date: {exc}") from exc
    elif col_type == "integer":
        return int(value) if pd.notna(value) else col_cfg.get("default", 0)
    elif col_type == "float":
        return float(value) if pd.notna(value) else col_cfg.get("default", 0)
    else:  # string
        default = col_cfg.get("default")
        try:
            is_na = pd.isna(value)
        except (TypeError, ValueError):
            is_na = value is None
        return default if is_na else str(value)


def process_upload(filepath: str, data_type: str, maker_id: str) -> UploadBatch:
    """Parse an uploaded file, validate, and store in staging — config-driven."""
    batch_id = str(uuid.uuid4())
    df = _read_file(filepath)

    errors = validate_upload(df, data_type)

    batch = UploadBatch(
        id=batch_id,
        data_type=data_type,
        filename=secure_filename(os.path.basename(filepath)),
        status="DRAFT" if errors else "PENDING",
        row_count=len(df),
        error_count=len(errors),
        errors_json=json.dumps(errors) if errors else None,
        maker_id=maker_id,
    )
    db.session.add(batch)

    # If no validation errors, load into staging using config
    if not errors:
        type_cfg = UPLOAD_CONFIG["data_types"][data_type]
        col_mapping = type_cfg["column_mapping"]
        staging_model = MODEL_REGISTRY[type_cfg["staging_table"]]

        try:
            for _, row in df.iterrows():
                record_data = {"upload_batch_id": batch_id}
                for col_name, col_cfg in col_mapping.items():
                    value = row.get(col_name, col_cfg.get("default"))
                    record_data[col_name] = _cast_value(value, col_cfg)

                # Add extra fields for allocation / reclass / interest-rate / distribution records
                if data_type in ("ALLOCATION", "ORG_RECLASS", "INTEREST_RATE", "DISTRIBUTION", "STATIC_ALLOC"):
                    record_data["status"] = "PENDING"
                    record_data["maker_id"] = maker_id

                db.session.add(staging_model(**record_data))
        except (ValueError, TypeError) as exc:
            batch.status = "DRAFT"
            cast_errors = [str(exc)]
            batch.error_count = len(cast_errors)
            batch.errors_json = json.dumps(cast_errors)
            db.session.commit()
            return batch

    db.session.commit()
    return batch


# ── Post-approval action executor ────────────────────────────────────────────

def run_post_approval(batch: UploadBatch, actor: str) -> list:
    """Execute post-approval actions configured for the batch data_type.

    Returns a list of PostApprovalLog rows (already committed).
    Action types:
        run_rules        — invoke run_allocation() for each rule_id in config
        stored_procedure — placeholder; logs the SP name with status=SUCCESS (POC)
    """
    from datetime import date
    from app.models.workflow import PostApprovalLog

    type_cfg = UPLOAD_CONFIG["data_types"].get(batch.data_type, {})
    post_approval = type_cfg.get("post_approval")
    if not post_approval:
        return []

    action_type = post_approval.get("type")
    logs = []

    if action_type == "run_rules":
        rule_ids = post_approval.get("rule_ids") or []
        if not rule_ids:
            log = PostApprovalLog(
                upload_batch_id=batch.id,
                action_type="run_rules",
                action_ref="(none)",
                status="SKIPPED",
                detail="No rule_ids configured in upload_config.json post_approval block.",
                executed_by=actor,
            )
            db.session.add(log)
            logs.append(log)
        else:
            from app.services.allocation_engine import run_allocation
            as_of_date = date.today()
            for rule_id in rule_ids:
                try:
                    result = run_allocation(int(rule_id), as_of_date, actor)
                    log = PostApprovalLog(
                        upload_batch_id=batch.id,
                        action_type="run_rules",
                        action_ref=str(rule_id),
                        status="SUCCESS" if result.status != "FAILED" else "FAILED",
                        detail=(
                            f"Rule {rule_id}: {result.output_row_count} output rows, "
                            f"{result.orphan_count} orphans, total {result.output_total:,.2f}"
                        ) if result.status != "FAILED" else result.error_message,
                        executed_by=actor,
                    )
                except Exception as exc:
                    log = PostApprovalLog(
                        upload_batch_id=batch.id,
                        action_type="run_rules",
                        action_ref=str(rule_id),
                        status="FAILED",
                        detail=str(exc),
                        executed_by=actor,
                    )
                db.session.add(log)
                logs.append(log)

    elif action_type == "stored_procedure":
        proc_name = post_approval.get("procedure_name", "(unnamed)")
        # POC placeholder — stored procedure execution is not yet implemented.
        # Replace the body of this branch with actual SP dispatch when ready.
        log = PostApprovalLog(
            upload_batch_id=batch.id,
            action_type="stored_procedure",
            action_ref=proc_name,
            status="SUCCESS",
            detail=f"[POC] Stored procedure '{proc_name}' was called (placeholder — no-op).",
            executed_by=actor,
        )
        db.session.add(log)
        logs.append(log)

    db.session.commit()
    return logs
