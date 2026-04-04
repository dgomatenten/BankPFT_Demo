"""Multi-task batch executor.

Runs allocation, FTP, data-file import/export, and custom SP steps in
order for a BatchDefinition.  Each step result is persisted to
BatchExecutionStep so the execution screen can show live status.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from app.models import db
from app.models.workflow import BatchDefinition, BatchExecution, BatchExecutionStep


def run_batch(definition_id: int, as_of_date: date, run_by: str) -> BatchExecution:
    """Execute all tasks in a BatchDefinition and return the BatchExecution record."""
    defn = db.session.get(BatchDefinition, definition_id)
    if not defn or not defn.is_active:
        raise ValueError(f"BatchDefinition {definition_id} not found or inactive")

    exec_id = str(uuid.uuid4())
    execution = BatchExecution(
        id=exec_id,
        definition_id=definition_id,
        as_of_date=as_of_date,
        status="RUNNING",
        run_by=run_by,
    )
    # Pre-create all step rows in PENDING state so the UI can show the plan
    for task in defn.tasks:
        execution.steps.append(BatchExecutionStep(
            execution_id=exec_id,
            step_order=task.step_order,
            task_type=task.task_type,
            ref_id=task.ref_id,
            label=task.label,
            status="PENDING",
        ))
    db.session.add(execution)
    db.session.commit()

    failed_count = 0
    for step in execution.steps:
        step.status = "RUNNING"
        step.started_at = datetime.utcnow()
        db.session.commit()

        try:
            _run_step(step, as_of_date, run_by)
            step.completed_at = datetime.utcnow()
            db.session.commit()
        except Exception as exc:
            step.status = "FAILED"
            step.error_message = str(exc)
            step.completed_at = datetime.utcnow()
            db.session.commit()
            failed_count += 1
            if not defn.continue_on_error:
                # Mark all remaining PENDING steps as SKIPPED
                for remaining in execution.steps:
                    if remaining.status == "PENDING":
                        remaining.status = "SKIPPED"
                db.session.commit()
                break

    execution.completed_at = datetime.utcnow()
    total = len(execution.steps)
    if failed_count == 0:
        execution.status = "COMPLETED"
    elif failed_count < total:
        execution.status = "PARTIAL"
    else:
        execution.status = "FAILED"
    db.session.commit()
    return execution


# ── Per-task dispatch ─────────────────────────────────────────────────────────

def _run_step(step: BatchExecutionStep, as_of_date: date, run_by: str) -> None:
    """Call the appropriate engine for a single task step."""
    t = step.task_type

    if t == "ALLOCATION":
        from app.services.allocation_engine import run_allocation
        result = run_allocation(int(step.ref_id), as_of_date, run_by)
        step.ref_run_id = result.id
        step.status = result.status
        step.summary = (
            f"{result.output_row_count} output rows, "
            f"{result.orphan_count} orphans, "
            f"output total {result.output_total:,.2f}"
        )
        if result.status == "FAILED":
            raise RuntimeError(result.error_message or "Allocation failed")

    elif t == "FTP":
        from app.services.ftp_engine import run_ftp
        result = run_ftp(as_of_date, run_by)
        step.ref_run_id = result.id
        step.status = result.status
        step.summary = (
            f"{result.instruments_matched} matched, "
            f"{result.instruments_skipped} skipped of "
            f"{result.instruments_processed} instruments"
        )
        if result.status == "FAILED":
            raise RuntimeError(result.error_message or "FTP run failed")

    elif t == "DATAFILE_IMPORT":
        from app.services.datafile_service import import_file, list_inbox_files
        # Scan inbox for the first file whose name contains the format_id (case-insensitive)
        inbox = list_inbox_files()
        match = next(
            (f["filename"] for f in inbox
             if step.ref_id.lower() in f["filename"].lower()),
            None,
        )
        # Fallback: take the first inbox file regardless of name
        if match is None and inbox:
            match = inbox[0]["filename"]
        if not match:
            raise RuntimeError(
                f"No file found in inbox for format '{step.ref_id}'. "
                "Place the file in uploads/inbox/ before running."
            )
        result = import_file(step.ref_id, match, run_by)
        step.ref_run_id = result.id
        step.status = result.status
        step.summary = f"{result.row_count} rows loaded, {result.error_count} errors — {match}"
        if result.status == "FAILED":
            raise RuntimeError(result.error_message or "Data file import failed")

    elif t == "DATAFILE_EXPORT":
        from app.services.datafile_service import export_data
        result = export_data(step.ref_id, run_by, as_of_date.isoformat())
        step.ref_run_id = result.id
        step.status = result.status
        step.summary = f"{result.row_count} rows exported — {result.filename}"
        if result.status == "FAILED":
            raise RuntimeError(result.error_message or "Data file export failed")

    elif t == "CUSTOM_SP":
        # Placeholder — will delegate to sp_runner once implemented
        step.status = "COMPLETED"
        step.summary = f"[PLACEHOLDER] Custom SP '{step.ref_id}' — not yet implemented"

    else:
        raise ValueError(f"Unknown task_type: {t!r}")
