"""Batch allocation engine — config-driven 'shredding' logic using Pandas.

The engine reads the AllocationRule from the database to determine WHICH tables
and join key to use, then looks up column definitions from allocation_config.json.

Flow:
  rule_config.json  →  UI form dropdowns  →  AllocationRule saved to DB
  allocation_config.json  →  column lists, orphan handling, engine defaults
  AllocationRule (DB)  →  source_table, lookup_table, output_table, join_key
  allocation_engine  →  merges DB rule + JSON config to execute
"""

import os
import json
import uuid
from datetime import datetime
import pandas as pd
from app.models import db
from app.models.staging import ProcInstData, ProcGlData
from app.models.allocation import RefStaticAllocation, RefOrgReclass, FctMgmtLedger
from app.models.workflow import AllocationRule, BatchRun

# ── Load configuration ──
_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "allocation_config.json")
with open(_CONFIG_PATH) as _f:
    ALLOC_CONFIG = json.load(_f)

# ── Model registry: maps table name → SQLAlchemy model ──
_SOURCE_MODELS = {
    "proc_inst_data": ProcInstData,
    "proc_gl_data": ProcGlData,
}

_LOOKUP_MODELS = {
    "ref_static_allocation": RefStaticAllocation,
    "ref_org_reclass": RefOrgReclass,
}


def run_allocation(rule_id: int, as_of_date, run_by: str) -> BatchRun:
    """Execute allocation shredding using the rule's DB config + JSON column definitions."""

    # ── 1. Load rule from DB ──
    rule = AllocationRule.query.get(rule_id)
    if not rule:
        raise ValueError(f"Rule {rule_id} not found")

    # ── 2. Resolve config for the tables chosen in the rule ──
    src_cfg = ALLOC_CONFIG["source_tables"].get(rule.source_table)
    lkp_cfg = ALLOC_CONFIG["lookup_tables"].get(rule.lookup_table)
    orphan_cfg = ALLOC_CONFIG["orphan_handling"]

    if not src_cfg:
        raise ValueError(f"No config for source table: {rule.source_table}")
    if not lkp_cfg:
        raise ValueError(f"No config for lookup table: {rule.lookup_table}")

    SourceModel = _SOURCE_MODELS.get(rule.source_table)
    LookupModel = _LOOKUP_MODELS.get(rule.lookup_table)
    if not SourceModel:
        raise ValueError(f"No model registered for: {rule.source_table}")
    if not LookupModel:
        raise ValueError(f"No model registered for: {rule.lookup_table}")

    join_key = rule.join_key  # from DB, not hardcoded

    batch_id = str(uuid.uuid4())
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
        # ── 3. Load source data using config columns ──
        date_col = src_cfg["date_filter_column"]
        source_rows = SourceModel.query.filter(
            getattr(SourceModel, date_col) == as_of_date
        ).all()
        if not source_rows:
            batch.status = "FAILED"
            batch.error_message = f"No data in {rule.source_table} for {as_of_date}."
            batch.completed_at = datetime.utcnow()
            db.session.commit()
            return batch

        source_data = pd.DataFrame([
            {col: getattr(r, col) for col in src_cfg["columns"]}
            for r in source_rows
        ])

        # ── 4. Load lookup ratios using config status filter ──
        alloc_rows = LookupModel.query.filter_by(status=lkp_cfg["status_filter"]).all()
        if alloc_rows:
            alloc_data = pd.DataFrame([
                {col: getattr(r, col) for col in lkp_cfg["columns"]}
                for r in alloc_rows
            ])
        else:
            alloc_data = pd.DataFrame(columns=lkp_cfg["columns"])

        # ── 5. Join using the rule's join key ──
        merged = source_data.merge(
            alloc_data, on=join_key, how=ALLOC_CONFIG.get("join_type", "left")
        )

        # Split: matched vs orphan
        id_col = lkp_cfg["id_column"]
        ratio_col = lkp_cfg["ratio_column"]
        target_org_col = lkp_cfg["target_org_column"]
        balance_cols = src_cfg["balance_columns"]
        acct_col = src_cfg["account_id_column"]

        matched = merged[merged[id_col].notna()].copy()
        orphan = merged[merged[id_col].isna()].copy()

        results = []

        # ── 6. Matched records: apply ratio ──
        if not matched.empty:
            for bal_col in balance_cols:
                matched[f"allocated_{bal_col}"] = matched[bal_col] * matched[ratio_col]

            for _, row in matched.iterrows():
                results.append(FctMgmtLedger(
                    batch_run_id=batch_id,
                    as_of_date=as_of_date,
                    allocation_id=row[id_col],
                    source_account_id=row[acct_col],
                    customer_id=row.get("customer_id", row.get(join_key, "")),
                    product_code=row.get("product_code", ""),
                    source_org_unit_id=row.get("org_unit_id", ""),
                    target_org_unit_id=row[target_org_col],
                    source_balance=row[balance_cols[0]],
                    allocated_balance=row[f"allocated_{balance_cols[0]}"],
                    allocated_income=row.get(f"allocated_{balance_cols[1]}", 0) if len(balance_cols) > 1 else 0,
                    ratio_applied=row[ratio_col],
                    is_orphan=False,
                ))

        # ── 7. Orphan records: use config default ratio ──
        if orphan_cfg["enabled"] and not orphan.empty:
            orphan_dedup = orphan.drop_duplicates(subset=[acct_col])
            default_ratio = orphan_cfg["default_ratio"]
            for _, row in orphan_dedup.iterrows():
                org = row.get("org_unit_id", "")
                results.append(FctMgmtLedger(
                    batch_run_id=batch_id,
                    as_of_date=as_of_date,
                    allocation_id=None,
                    source_account_id=row[acct_col],
                    customer_id=row.get("customer_id", row.get(join_key, "")),
                    product_code=row.get("product_code", ""),
                    source_org_unit_id=org,
                    target_org_unit_id=org,
                    source_balance=row[balance_cols[0]],
                    allocated_balance=row[balance_cols[0]] * default_ratio,
                    allocated_income=row[balance_cols[1]] * default_ratio if len(balance_cols) > 1 else 0,
                    ratio_applied=default_ratio,
                    is_orphan=True,
                ))

        db.session.add_all(results)

        # ── 8. Update batch stats ──
        batch.source_row_count = len(source_data)
        batch.output_row_count = len(results)
        batch.orphan_count = len(orphan_dedup) if not orphan.empty else 0
        batch.source_total = float(source_data[balance_cols[0]].sum())
        batch.output_total = sum(r.allocated_balance for r in results)
        batch.status = "COMPLETED"
        batch.completed_at = datetime.utcnow()
        db.session.commit()

    except Exception as e:
        batch.status = "FAILED"
        batch.error_message = str(e)
        batch.completed_at = datetime.utcnow()
        db.session.commit()
        raise

    return batch

    return batch
