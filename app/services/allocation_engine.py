"""Batch allocation engine — config-driven 'shredding' logic using Pandas."""

import os
import json
import uuid
from datetime import datetime
import pandas as pd
from app.models import db
from app.models.staging import ProcInstData
from app.models.allocation import RefStaticAllocation, FctMgmtLedger
from app.models.workflow import AllocationRule, BatchRun

# ── Load configuration ──
_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "allocation_config.json")
with open(_CONFIG_PATH) as _f:
    ALLOC_CONFIG = json.load(_f)


def run_allocation(rule_id: int, as_of_date, run_by: str) -> BatchRun:
    """Execute the allocation shredding for a given rule and date."""
    src_cfg = ALLOC_CONFIG["source"]
    lkp_cfg = ALLOC_CONFIG["lookup"]
    join_cfg = ALLOC_CONFIG["join"]
    out_cfg = ALLOC_CONFIG["output"]
    orphan_cfg = ALLOC_CONFIG["orphan_handling"]

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
        # Load source data using config columns
        source_rows = ProcInstData.query.filter(
            getattr(ProcInstData, src_cfg["date_filter_column"]) == as_of_date
        ).all()
        if not source_rows:
            batch.status = "FAILED"
            batch.error_message = "No processed instrument data for the selected date."
            batch.completed_at = datetime.utcnow()
            db.session.commit()
            return batch

        source_data = pd.DataFrame([
            {col: getattr(r, col) for col in src_cfg["columns"]}
            for r in source_rows
        ])

        # Load allocation ratios using config status filter
        alloc_rows = RefStaticAllocation.query.filter_by(status=lkp_cfg["status_filter"]).all()
        if alloc_rows:
            alloc_data = pd.DataFrame([
                {col: getattr(r, col) for col in lkp_cfg["columns"]}
                for r in alloc_rows
            ])
        else:
            alloc_data = pd.DataFrame(columns=lkp_cfg["columns"])

        # Join source with allocations using config join key
        join_key = join_cfg["key"]
        merged = source_data.merge(alloc_data, on=join_key, how=join_cfg["type"])

        # Split: matched vs orphan
        id_col = lkp_cfg["columns"][0]  # allocation_id
        matched = merged[merged[id_col].notna()].copy()
        orphan = merged[merged[id_col].isna()].copy()

        results = []
        ratio_col = out_cfg["ratio_column"]
        balance_cols = out_cfg["balance_columns"]

        # Matched records: apply ratio from config
        if not matched.empty:
            for bal_col in balance_cols:
                matched[f"allocated_{bal_col}"] = matched[bal_col] * matched[ratio_col]

            for _, row in matched.iterrows():
                results.append(FctMgmtLedger(
                    batch_run_id=batch_id,
                    as_of_date=as_of_date,
                    allocation_id=row["allocation_id"],
                    source_account_id=row["account_id"],
                    customer_id=row[join_key],
                    product_code=row["product_code"],
                    source_org_unit_id=row["org_unit_id"],
                    target_org_unit_id=row["target_org_unit_id"],
                    source_balance=row["balance"],
                    allocated_balance=row["allocated_balance"],
                    allocated_income=row["allocated_interest_income"],
                    ratio_applied=row[ratio_col],
                    is_orphan=False,
                ))

        # Orphan records: use config default ratio and target org
        if orphan_cfg["enabled"] and not orphan.empty:
            orphan_dedup = orphan.drop_duplicates(subset=["account_id"])
            default_ratio = orphan_cfg["default_ratio"]
            for _, row in orphan_dedup.iterrows():
                results.append(FctMgmtLedger(
                    batch_run_id=batch_id,
                    as_of_date=as_of_date,
                    allocation_id=None,
                    source_account_id=row["account_id"],
                    customer_id=row[join_key],
                    product_code=row["product_code"],
                    source_org_unit_id=row["org_unit_id"],
                    target_org_unit_id=row["org_unit_id"],
                    source_balance=row["balance"],
                    allocated_balance=row["balance"] * default_ratio,
                    allocated_income=row["interest_income"] * default_ratio,
                    ratio_applied=default_ratio,
                    is_orphan=True,
                ))

        db.session.add_all(results)

        # Update batch stats
        batch.source_row_count = len(source_data)
        batch.output_row_count = len(results)
        batch.orphan_count = len(orphan_dedup) if not orphan.empty else 0
        batch.source_total = float(source_data["balance"].sum())
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
