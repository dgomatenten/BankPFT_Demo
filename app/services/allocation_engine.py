"""Batch allocation engine — config-driven shredding with debit/credit offset entries,
per-dimension source filtering, and flexible output dimension mapping.

Flow:
  rule_config.json      →  UI dropdowns for rule creation / import
  allocation_config.json →  column lists, orphan handling, engine defaults
  AllocationRule (DB)   →  all runtime parameters (table, join, dim configs)
  allocation_engine     →  executes; writes DEBIT + CREDIT rows to output table
"""

import os
import json
import uuid
from datetime import datetime
import pandas as pd
from app.models import db
from app.models.staging import ProcInstData, ProcGlData
from app.models.allocation import (
    RefStaticAllocation, RefOrgReclass, RefStaticDistribution, RefStaticAlloc,
    FctMgmtLedger, FctMgmtInstrument,
)
from app.models.workflow import AllocationRule, BatchRun

# ── Load configuration ──
_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "allocation_config.json")
with open(_CONFIG_PATH) as _f:
    ALLOC_CONFIG = json.load(_f)

# ── Model registries ──
_SOURCE_MODELS = {
    "proc_inst_data": ProcInstData,
    "proc_gl_data":   ProcGlData,
}

_LOOKUP_MODELS = {
    "ref_static_allocation":  RefStaticAllocation,
    "ref_org_reclass":        RefOrgReclass,
    "ref_static_distribution": RefStaticDistribution,
    "ref_static_alloc":       RefStaticAlloc,
}

_OUTPUT_MODELS = {
    "fct_mgmt_ledger":     FctMgmtLedger,
    "fct_mgmt_instrument": FctMgmtInstrument,
}

# ── Batch log directory ──
BATCH_LOG_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "instance", "batch_logs"
)


class _BatchLogger:
    """Writes timestamped processing log entries to a per-batch file."""

    def __init__(self, batch_id: str):
        os.makedirs(BATCH_LOG_DIR, exist_ok=True)
        self.path = os.path.join(BATCH_LOG_DIR, f"batch_{batch_id}.log")
        self._fh = open(self.path, "w", encoding="utf-8")

    def log(self, level: str, msg: str) -> None:
        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        self._fh.write(f"[{ts}] [{level:<8}] {msg}\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()


# ──────────────────────────────────────────────────────────────────────────────
# Helper: general row filter (existing logic, unchanged)
# ──────────────────────────────────────────────────────────────────────────────
def _apply_filters(df: pd.DataFrame, filter_json: str | None) -> pd.DataFrame:
    """Apply user-defined filter conditions (stored as JSON) to a DataFrame."""
    if not filter_json:
        return df
    try:
        filt = json.loads(filter_json)
    except (json.JSONDecodeError, TypeError):
        return df

    conditions = filt.get("conditions", [])
    if not conditions:
        return df

    logic = filt.get("logic", "AND")
    masks = []

    for cond in conditions:
        col = cond.get("field")
        op  = cond.get("operator")
        val = cond.get("value", "")
        if not col or not op or col not in df.columns:
            continue

        series = df[col]

        if op == "eq":
            m = series.astype(str) == val
        elif op == "neq":
            m = series.astype(str) != val
        elif op == "gt":
            m = pd.to_numeric(series, errors="coerce") > float(val)
        elif op == "gte":
            m = pd.to_numeric(series, errors="coerce") >= float(val)
        elif op == "lt":
            m = pd.to_numeric(series, errors="coerce") < float(val)
        elif op == "lte":
            m = pd.to_numeric(series, errors="coerce") <= float(val)
        elif op == "between":
            parts = [v.strip() for v in val.split(",")]
            if len(parts) == 2:
                num = pd.to_numeric(series, errors="coerce")
                m = (num >= float(parts[0])) & (num <= float(parts[1]))
            else:
                continue
        elif op == "in":
            vals = {v.strip() for v in val.split(",")}
            m = series.astype(str).isin(vals)
        elif op == "not_in":
            vals = {v.strip() for v in val.split(",")}
            m = ~series.astype(str).isin(vals)
        elif op == "contains":
            m = series.astype(str).str.contains(val, case=False, na=False)
        elif op == "starts_with":
            m = series.astype(str).str.startswith(val, na=False)
        else:
            continue

        masks.append(m)

    if not masks:
        return df

    if logic == "OR":
        combined = masks[0]
        for m in masks[1:]:
            combined = combined | m
    else:
        combined = masks[0]
        for m in masks[1:]:
            combined = combined & m

    return df[combined].reset_index(drop=True)


# ──────────────────────────────────────────────────────────────────────────────
# Helper: source dimension member filter
# ──────────────────────────────────────────────────────────────────────────────
def _apply_source_dim_filters(
    df: pd.DataFrame,
    source_dim_cfg: dict,
    dim_columns: list[str],
) -> pd.DataFrame:
    """For each dimension, keep only the specified members when mode='specific'."""
    for dim in dim_columns:
        cfg = source_dim_cfg.get(dim, {"mode": "all"})
        if cfg.get("mode") == "specific":
            members = [m.strip() for m in cfg.get("members", []) if m.strip()]
            if members and dim in df.columns:
                df = df[df[dim].astype(str).isin(members)]
    return df.reset_index(drop=True)


# ──────────────────────────────────────────────────────────────────────────────
# Helper: resolve a single output dimension value for the DEBIT (target) entry
# ──────────────────────────────────────────────────────────────────────────────
def _resolve_dim_value(
    row: pd.Series,
    dim_col: str,
    output_dim_cfg: dict,
    fallback: str,
    target_org_col: str,
) -> str:
    """
    Modes:
      same_as_source — use the source value (fallback)
      lookup         — read from a lookup-joined column (default: target_org_col)
      fixed          — use the hardcoded 'value' from the config
    """
    cfg  = output_dim_cfg.get(dim_col, {"mode": "same_as_source"})
    mode = cfg.get("mode", "same_as_source")

    if mode == "lookup":
        col = cfg.get("lookup_column", target_org_col)
        return str(row.get(col, fallback))
    if mode == "fixed":
        return str(cfg.get("value", fallback))
    return str(fallback)  # same_as_source


# ──────────────────────────────────────────────────────────────────────────────
# Main: run one allocation batch
# ──────────────────────────────────────────────────────────────────────────────
def run_allocation(rule_id: int, as_of_date, run_by: str) -> BatchRun:
    """Execute allocation shredding; produces DEBIT + CREDIT entries in the output table.

    Allocation methods
    ------------------
    RATIO         — join source to a lookup table, apply ratio-based shredding (default).
    DISTRIBUTION  — same engine path as RATIO but lookup table is ref_static_distribution;
                    the target_dim column drives flexible output dimension mapping.
    STATIC        — no lookup join; each source row maps 1:1 to the output at ratio=1.0.
                    Output dimensions come from output_dim_json (fixed / same_as_source).
                    Suitable for instrument aggregation and simple reclassification.
    """

    # ── 1. Load rule ──
    rule = AllocationRule.query.get(rule_id)
    if not rule:
        raise ValueError(f"Rule {rule_id} not found")

    alloc_method = (getattr(rule, "allocation_method", None) or "RATIO").strip().upper()
    if alloc_method not in ("RATIO", "DISTRIBUTION", "STATIC"):
        alloc_method = "RATIO"

    # ── 2. Resolve config ──
    src_cfg    = ALLOC_CONFIG["source_tables"].get(rule.source_table)
    orphan_cfg = ALLOC_CONFIG["orphan_handling"]

    if not src_cfg:
        raise ValueError(f"No config for source table: {rule.source_table}")

    SourceModel = _SOURCE_MODELS.get(rule.source_table)
    OutputModel = _OUTPUT_MODELS.get(rule.output_table, FctMgmtLedger)

    if not SourceModel:
        raise ValueError(f"No model registered for source: {rule.source_table}")

    # For lookup-based methods resolve lookup config/model; STATIC needs neither
    if alloc_method in ("RATIO", "DISTRIBUTION"):
        lkp_cfg    = ALLOC_CONFIG["lookup_tables"].get(rule.lookup_table)
        LookupModel = _LOOKUP_MODELS.get(rule.lookup_table)
        if not lkp_cfg:
            raise ValueError(f"No config for lookup table: {rule.lookup_table}")
        if not LookupModel:
            raise ValueError(f"No model registered for lookup: {rule.lookup_table}")
    else:
        lkp_cfg     = None
        LookupModel = None

    # ── Parse new dimension configs ──
    source_dim_cfg = json.loads(rule.source_dim_json) if rule.source_dim_json else {}
    output_dim_cfg = json.loads(rule.output_dim_json) if rule.output_dim_json else {}
    credit_dim_cfg = json.loads(rule.credit_dim_json) if rule.credit_dim_json else {}

    # Resolve entry mode: new entry_mode field takes precedence over legacy generate_offset
    raw_mode = (rule.entry_mode or "").strip().upper() if getattr(rule, "entry_mode", None) else ""
    if raw_mode not in ("BOTH", "DEBIT_ONLY", "CREDIT_ONLY"):
        # Fallback to legacy boolean
        raw_mode = "BOTH" if (rule.generate_offset if rule.generate_offset is not None else True) else "DEBIT_ONLY"
    emit_debit  = raw_mode in ("BOTH", "DEBIT_ONLY")
    emit_credit = raw_mode in ("BOTH", "CREDIT_ONLY")

    join_key   = rule.join_key
    batch_id   = str(uuid.uuid4())
    logger     = _BatchLogger(batch_id)
    _t_start   = datetime.utcnow()

    logger.log("START",  f"Batch '{batch_id[:8]}...' initiated by {run_by}")
    logger.log("RULE",   f"Rule #{rule_id}: '{rule.name}'")
    logger.log("RULE",   f"  method={alloc_method} | source={rule.source_table} | lookup={rule.lookup_table} | output={rule.output_table}")
    logger.log("RULE",   f"  entry_mode={raw_mode} | join_key={join_key}")
    if source_dim_cfg:
        logger.log("RULE", f"  source_dim_filters: {list(source_dim_cfg.keys())}")
    if output_dim_cfg:
        logger.log("RULE", f"  output_dim_mapping: {list(output_dim_cfg.keys())}")

    batch = BatchRun(
        id=batch_id,
        rule_id=rule_id,
        as_of_date=as_of_date,
        status="RUNNING",
        run_by=run_by,
        started_at=datetime.utcnow(),
    )
    db.session.add(batch)
    db.session.commit()

    try:
        # ── 3. Load source data ──
        date_col    = src_cfg["date_filter_column"]
        logger.log("QUERY",  f"Loading source data from '{rule.source_table}' where {date_col}={as_of_date}")
        source_rows = SourceModel.query.filter(
            getattr(SourceModel, date_col) == as_of_date
        ).all()
        if not source_rows:
            logger.log("ERROR",  f"No rows in '{rule.source_table}' for as_of_date={as_of_date}")
            batch.status        = "FAILED"
            batch.error_message = f"No data in {rule.source_table} for {as_of_date}."
            batch.completed_at  = datetime.utcnow()
            db.session.commit()
            return batch

        source_data = pd.DataFrame([
            {col: getattr(r, col) for col in src_cfg["columns"]}
            for r in source_rows
        ])
        logger.log("DATA",   f"Source rows loaded: {len(source_data):,}")

        # ── 3b. General filter (filter_json) ──
        _pre_filter = len(source_data)
        source_data = _apply_filters(source_data, rule.filter_json)
        if rule.filter_json:
            logger.log("FILTER", f"Data filter applied: {_pre_filter:,} → {len(source_data):,} rows")
        else:
            logger.log("FILTER", "No data filter configured — all source rows retained")
        if source_data.empty:
            logger.log("ERROR",  "No rows remain after applying data filters")
            batch.status        = "FAILED"
            batch.error_message = "No rows remain after applying data filters."
            batch.completed_at  = datetime.utcnow()
            db.session.commit()
            return batch

        # ── 3c. Per-dimension source member filter ──
        _pre_dim = len(source_data)
        source_data = _apply_source_dim_filters(
            source_data, source_dim_cfg, src_cfg["dimension_columns"]
        )
        if source_dim_cfg:
            logger.log("FILTER", f"Source dimension filter applied: {_pre_dim:,} → {len(source_data):,} rows")
        else:
            logger.log("FILTER", "No source dimension filters configured")
        if source_data.empty:
            logger.log("ERROR",  "No rows remain after applying source dimension filters")
            batch.status        = "FAILED"
            batch.error_message = "No rows remain after applying source dimension filters."
            batch.completed_at  = datetime.utcnow()
            db.session.commit()
            return batch

        # ── 4. Load lookup ratios (RATIO / DISTRIBUTION) or skip (STATIC) ──
        balance_cols = src_cfg["balance_columns"]
        acct_col     = src_cfg["account_id_column"]
        results       = []
        _debit_count  = 0
        _credit_count = 0
        orphan_dedup  = pd.DataFrame()

        if alloc_method in ("RATIO", "DISTRIBUTION"):
            # ── 4a. Load lookup table ──
            logger.log("QUERY",  f"Loading lookup ratios from '{rule.lookup_table}' (status={lkp_cfg['status_filter']})")
            alloc_rows = LookupModel.query.filter_by(status=lkp_cfg["status_filter"]).all()
            alloc_data = (
                pd.DataFrame([
                    {col: getattr(r, col) for col in lkp_cfg["columns"]}
                    for r in alloc_rows
                ])
                if alloc_rows
                else pd.DataFrame(columns=lkp_cfg["columns"])
            )
            logger.log("DATA",   f"Lookup ratios loaded: {len(alloc_data):,} rows")

            # ── 5. Join source ↔ lookup ──
            join_col_list = [k.strip() for k in join_key.split(",") if k.strip()]
            if not join_col_list:
                raise ValueError(f"Rule '{rule.name}' has no join key configured.")
            primary_join_col = join_col_list[0]
            pandas_join = join_col_list[0] if len(join_col_list) == 1 else join_col_list
            logger.log("JOIN",   f"Merging source ↔ lookup on {pandas_join!r} ({ALLOC_CONFIG.get('join_type', 'left')} join)")
            merged = source_data.merge(
                alloc_data, on=pandas_join, how=ALLOC_CONFIG.get("join_type", "left")
            )

            id_col         = lkp_cfg["id_column"]
            ratio_col      = lkp_cfg["ratio_column"]
            target_org_col = lkp_cfg["target_org_column"]

            matched = merged[merged[id_col].notna()].copy()
            orphan  = merged[merged[id_col].isna()].copy()
            logger.log("JOIN",    f"Post-merge: {len(matched):,} matched rows, {len(orphan):,} orphan rows")

            # ── 6. Matched rows: DEBIT + optional CREDIT ──
            logger.log("PROCESS", f"Generating entries for {len(matched):,} matched rows"
                                  f" (emit_debit={emit_debit}, emit_credit={emit_credit})")
            for _, row in matched.iterrows():
                src_acct = str(row.get(acct_col, ""))
                src_org  = str(row.get("org_unit_id", ""))
                src_cust = str(row.get("customer_id", row.get(primary_join_col, "")))
                src_prod = str(row.get("product_code", ""))
                src_bal  = float(row[balance_cols[0]])
                ratio    = float(row[ratio_col])

                alloc_bal = src_bal * ratio
                alloc_inc = float(row[balance_cols[1]]) * ratio if len(balance_cols) > 1 else 0.0

                tgt_org  = _resolve_dim_value(row, "org_unit_id",  output_dim_cfg, src_org,  target_org_col)
                out_cust = _resolve_dim_value(row, "customer_id",  output_dim_cfg, src_cust, target_org_col)
                out_prod = _resolve_dim_value(row, "product_code", output_dim_cfg, src_prod, target_org_col)
                out_acct = _resolve_dim_value(row, acct_col,       output_dim_cfg, src_acct, target_org_col)

                if emit_debit:
                    _debit_count += 1
                    results.append(OutputModel(
                        batch_run_id=batch_id,
                        as_of_date=as_of_date,
                        entry_type="DEBIT",
                        allocation_id=str(row[id_col]),
                        source_account_id=out_acct,
                        customer_id=out_cust,
                        product_code=out_prod,
                        source_org_unit_id=src_org,
                        target_org_unit_id=tgt_org,
                        source_balance=src_bal,
                        allocated_balance=alloc_bal,
                        allocated_income=alloc_inc,
                        ratio_applied=ratio,
                        is_orphan=False,
                    ))

                if emit_credit:
                    _credit_count += 1
                    crd_org  = _resolve_dim_value(row, "org_unit_id",  credit_dim_cfg, src_org,  target_org_col)
                    crd_cust = _resolve_dim_value(row, "customer_id",  credit_dim_cfg, src_cust, target_org_col)
                    crd_prod = _resolve_dim_value(row, "product_code", credit_dim_cfg, src_prod, target_org_col)
                    crd_acct = _resolve_dim_value(row, acct_col,       credit_dim_cfg, src_acct, target_org_col)
                    results.append(OutputModel(
                        batch_run_id=batch_id,
                        as_of_date=as_of_date,
                        entry_type="CREDIT",
                        allocation_id=str(row[id_col]),
                        source_account_id=crd_acct,
                        customer_id=crd_cust,
                        product_code=crd_prod,
                        source_org_unit_id=src_org,
                        target_org_unit_id=crd_org,
                        source_balance=src_bal,
                        allocated_balance=-alloc_bal,
                        allocated_income=-alloc_inc,
                        ratio_applied=ratio,
                        is_orphan=False,
                    ))

            logger.log("PROCESS", f"  → DEBIT entries: {_debit_count:,} | CREDIT entries: {_credit_count:,}")

            # ── 7. Orphan rows (no lookup match) ──
            if orphan_cfg["enabled"] and not orphan.empty:
                orphan_dedup  = orphan.drop_duplicates(subset=[acct_col])
                default_ratio = orphan_cfg["default_ratio"]
                logger.log("ORPHAN",  f"Processing {len(orphan_dedup):,} orphan rows (default_ratio={default_ratio})")
                for _, row in orphan_dedup.iterrows():
                    src_org   = str(row.get("org_unit_id", ""))
                    src_bal   = float(row[balance_cols[0]])
                    alloc_inc = float(row[balance_cols[1]]) * default_ratio if len(balance_cols) > 1 else 0.0
                    results.append(OutputModel(
                        batch_run_id=batch_id,
                        as_of_date=as_of_date,
                        entry_type="DEBIT",
                        allocation_id=None,
                        source_account_id=str(row.get(acct_col, "")),
                        customer_id=str(row.get("customer_id", row.get(primary_join_col, ""))),
                        product_code=str(row.get("product_code", "")),
                        source_org_unit_id=src_org,
                        target_org_unit_id=src_org,
                        source_balance=src_bal,
                        allocated_balance=src_bal * default_ratio,
                        allocated_income=alloc_inc,
                        ratio_applied=default_ratio,
                        is_orphan=True,
                    ))

        else:
            # ── STATIC method: direct 1:1 pass-through, ratio = 1.0 ──
            logger.log("PROCESS", f"Static allocation: {len(source_data):,} source rows → direct pass-through"
                                  f" (emit_debit={emit_debit}, emit_credit={emit_credit})")
            for _, row in source_data.iterrows():
                src_acct = str(row.get(acct_col, ""))
                src_org  = str(row.get("org_unit_id", ""))
                src_cust = str(row.get("customer_id", ""))
                src_prod = str(row.get("product_code", ""))
                src_bal  = float(row[balance_cols[0]])
                alloc_inc = float(row[balance_cols[1]]) if len(balance_cols) > 1 else 0.0

                # Output dimensions: same_as_source or fixed (lookup mode not applicable)
                tgt_org  = _resolve_dim_value(row, "org_unit_id",  output_dim_cfg, src_org,  src_org)
                out_cust = _resolve_dim_value(row, "customer_id",  output_dim_cfg, src_cust, src_org)
                out_prod = _resolve_dim_value(row, "product_code", output_dim_cfg, src_prod, src_org)
                out_acct = _resolve_dim_value(row, acct_col,       output_dim_cfg, src_acct, src_org)

                if emit_debit:
                    _debit_count += 1
                    results.append(OutputModel(
                        batch_run_id=batch_id,
                        as_of_date=as_of_date,
                        entry_type="DEBIT",
                        allocation_id=None,
                        source_account_id=out_acct,
                        customer_id=out_cust,
                        product_code=out_prod,
                        source_org_unit_id=src_org,
                        target_org_unit_id=tgt_org,
                        source_balance=src_bal,
                        allocated_balance=src_bal,
                        allocated_income=alloc_inc,
                        ratio_applied=1.0,
                        is_orphan=False,
                    ))

                if emit_credit:
                    _credit_count += 1
                    crd_org  = _resolve_dim_value(row, "org_unit_id",  credit_dim_cfg, src_org,  src_org)
                    crd_cust = _resolve_dim_value(row, "customer_id",  credit_dim_cfg, src_cust, src_org)
                    crd_prod = _resolve_dim_value(row, "product_code", credit_dim_cfg, src_prod, src_org)
                    crd_acct = _resolve_dim_value(row, acct_col,       credit_dim_cfg, src_acct, src_org)
                    results.append(OutputModel(
                        batch_run_id=batch_id,
                        as_of_date=as_of_date,
                        entry_type="CREDIT",
                        allocation_id=None,
                        source_account_id=crd_acct,
                        customer_id=crd_cust,
                        product_code=crd_prod,
                        source_org_unit_id=src_org,
                        target_org_unit_id=crd_org,
                        source_balance=src_bal,
                        allocated_balance=-src_bal,
                        allocated_income=-alloc_inc,
                        ratio_applied=1.0,
                        is_orphan=False,
                    ))

            logger.log("PROCESS", f"  → DEBIT entries: {_debit_count:,} | CREDIT entries: {_credit_count:,}")

        # ── 8. Write results ──
        db.session.add_all(results)
        logger.log("DB",      f"Writing {len(results):,} output rows to '{rule.output_table}'")

        # ── 9. Update batch stats (DEBIT rows drive totals) ──
        debit_rows = [r for r in results if r.entry_type == "DEBIT"]
        batch.source_row_count = len(source_data)
        batch.output_row_count = len(results)
        batch.orphan_count     = len(orphan_dedup)
        batch.source_total     = float(source_data[balance_cols[0]].sum())
        batch.output_total     = sum(r.allocated_balance for r in debit_rows)
        batch.status           = "COMPLETED"
        batch.completed_at     = datetime.utcnow()
        _elapsed = (datetime.utcnow() - _t_start).total_seconds()
        logger.log("SUMMARY",  f"source_rows={batch.source_row_count:,}  output_rows={batch.output_row_count:,}  orphans={batch.orphan_count:,}")
        logger.log("SUMMARY",  f"source_total={batch.source_total:,.2f}  output_total={batch.output_total:,.2f}  variance={batch.source_total - batch.output_total:,.2f}")
        logger.log("COMPLETE", f"Batch completed in {_elapsed:.2f}s")
        db.session.commit()

    except Exception as e:
        logger.log("ERROR",  f"Unhandled exception: {e}")
        logger.log("FAILED", "Batch terminated — status=FAILED")
        batch.status        = "FAILED"
        batch.error_message = str(e)
        batch.completed_at  = datetime.utcnow()
        db.session.commit()
        raise
    finally:
        logger.close()

    return batch
