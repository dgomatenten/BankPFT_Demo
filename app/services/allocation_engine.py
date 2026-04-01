"""Batch allocation engine — the 'shredding' logic using Pandas."""

import uuid
from datetime import datetime
import pandas as pd
from app.models import db
from app.models.staging import ProcInstData
from app.models.allocation import RefStaticAllocation, FctMgmtLedger
from app.models.workflow import AllocationRule, BatchRun


def run_allocation(rule_id: int, as_of_date, run_by: str) -> BatchRun:
    """Execute the allocation shredding for a given rule and date."""
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
        # Load source data
        source_rows = ProcInstData.query.filter(ProcInstData.as_of_date == as_of_date).all()
        if not source_rows:
            batch.status = "FAILED"
            batch.error_message = "No processed instrument data for the selected date."
            batch.completed_at = datetime.utcnow()
            db.session.commit()
            return batch

        source_data = pd.DataFrame([{
            "account_id": r.account_id,
            "customer_id": r.customer_id,
            "product_code": r.product_code,
            "org_unit_id": r.org_unit_id,
            "balance": r.balance,
            "interest_income": r.interest_income,
        } for r in source_rows])

        # Load allocation ratios (APPROVED only)
        alloc_rows = RefStaticAllocation.query.filter_by(status="APPROVED").all()
        if alloc_rows:
            alloc_data = pd.DataFrame([{
                "allocation_id": r.allocation_id,
                "customer_id": r.customer_id,
                "source_org_unit_id": r.source_org_unit_id,
                "target_org_unit_id": r.target_org_unit_id,
                "ratio": r.ratio,
            } for r in alloc_rows])
        else:
            alloc_data = pd.DataFrame(
                columns=["allocation_id", "customer_id", "source_org_unit_id",
                         "target_org_unit_id", "ratio"]
            )

        # Join source with allocations
        merged = source_data.merge(alloc_data, on="customer_id", how="left")

        # Split: matched vs orphan
        matched = merged[merged["allocation_id"].notna()].copy()
        orphan = merged[merged["allocation_id"].isna()].copy()

        results = []

        # Matched records: apply ratio
        if not matched.empty:
            matched["allocated_balance"] = matched["balance"] * matched["ratio"]
            matched["allocated_income"] = matched["interest_income"] * matched["ratio"]
            for _, row in matched.iterrows():
                results.append(FctMgmtLedger(
                    batch_run_id=batch_id,
                    as_of_date=as_of_date,
                    allocation_id=row["allocation_id"],
                    source_account_id=row["account_id"],
                    customer_id=row["customer_id"],
                    product_code=row["product_code"],
                    source_org_unit_id=row["org_unit_id"],
                    target_org_unit_id=row["target_org_unit_id"],
                    source_balance=row["balance"],
                    allocated_balance=row["allocated_balance"],
                    allocated_income=row["allocated_income"],
                    ratio_applied=row["ratio"],
                    is_orphan=False,
                ))

        # Orphan records: 100% to original org unit
        if not orphan.empty:
            orphan_dedup = orphan.drop_duplicates(subset=["account_id"])
            for _, row in orphan_dedup.iterrows():
                results.append(FctMgmtLedger(
                    batch_run_id=batch_id,
                    as_of_date=as_of_date,
                    allocation_id=None,
                    source_account_id=row["account_id"],
                    customer_id=row["customer_id"],
                    product_code=row["product_code"],
                    source_org_unit_id=row["org_unit_id"],
                    target_org_unit_id=row["org_unit_id"],
                    source_balance=row["balance"],
                    allocated_balance=row["balance"],
                    allocated_income=row["interest_income"],
                    ratio_applied=1.0,
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
