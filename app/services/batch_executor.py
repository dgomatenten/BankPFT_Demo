"""Multi-task batch executor.

Runs allocation, FTP, data-file import/export, and custom SP steps in
order for a BatchDefinition.  Each step result is persisted to
BatchExecutionStep so the execution screen can show live status.
"""
from __future__ import annotations

import uuid
from datetime import date
from app.core.time_utils import utc_now

from app.models import db
from app.models.workflow import BatchDefinition, BatchExecution, BatchExecutionStep


def _get_processing_date(as_of_date: date) -> date:
    """Return the active 'processing_date' operation variable value, or fall
    back to the batch as_of_date if the variable is unset or inactive."""
    try:
        from app.models.workflow import OperationVariable
        var = OperationVariable.query.filter_by(key="processing_date", is_active=True).first()
        if var and var.value:
            from datetime import datetime
            return datetime.strptime(var.value, "%Y-%m-%d").date()
    except Exception:
        pass
    return as_of_date


def run_batch(definition_id: int, as_of_date: date, run_by: str) -> BatchExecution:
    """Execute all tasks in a BatchDefinition and return the BatchExecution record."""
    defn = db.session.get(BatchDefinition, definition_id)
    if not defn or not defn.is_active:
        raise ValueError(f"BatchDefinition {definition_id} not found or inactive")

    # Resolve processing_date from operation variables (falls back to as_of_date)
    processing_date = _get_processing_date(as_of_date)

    exec_id = str(uuid.uuid4())
    
    from app.core.batch_logger import BatchLogger
    logger = BatchLogger(f"execution_{exec_id}")
    logger.info(f"Starting Multi-task Batch Execution for definition '{defn.name}' (ID: {defn.id})")
    logger.info(f"Run ID: {exec_id} | As-of: {as_of_date} | Run By: {run_by}")
    
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
            params_json=task.params_json,
            label=task.label,
            status="PENDING",
        ))
    db.session.add(execution)
    db.session.commit()

    failed_count = 0
    for step in execution.steps:
        step.status = "RUNNING"
        step.started_at = utc_now()
        db.session.commit()
        
        logger.info(f"\n--- Starting Step {step.step_order}: [{step.task_type}] {step.label or step.ref_id} ---")

        try:
            _run_step(step, processing_date, as_of_date, run_by)
            step.completed_at = utc_now()
            db.session.commit()
            logger.info(f"Step {step.step_order} completed successfully.\nSummary: {step.summary}")
        except Exception as exc:
            step.status = "FAILED"
            step.error_message = str(exc)
            step.completed_at = utc_now()
            db.session.commit()
            failed_count += 1
            logger.error(f"Step {step.step_order} FAILED: {exc}")
            
            if not defn.continue_on_error:
                logger.warning("Continue-on-error is false. Halting execution pipeline.")
                # Mark all remaining PENDING steps as SKIPPED
                for remaining in execution.steps:
                    if remaining.status == "PENDING":
                        remaining.status = "SKIPPED"
                        logger.warning(f"Skipped Step {remaining.step_order}: [{remaining.task_type}]")
                db.session.commit()
                break

    execution.completed_at = utc_now()
    total = len(execution.steps)
    if failed_count == 0:
        execution.status = "COMPLETED"
    elif failed_count < total:
        execution.status = "PARTIAL"
    else:
        execution.status = "FAILED"
        
    logger.info(f"\nBatch Execution finished with status: {execution.status}")
    db.session.commit()
    logger.close()
    return execution


# ── Per-task dispatch ─────────────────────────────────────────────────────────

def _run_step(
    step: BatchExecutionStep,
    processing_date: date,
    original_date: date,
    run_by: str,
) -> None:
    """Call the appropriate engine for a single task step.

    processing_date — effective date used by allocation/FTP/datafile engines
                      (= processing_date op var, or batch form date as fallback)
    original_date   — the date the user typed on the batch run form; used as
                      the ``{as_of_date}`` token in CUSTOM_SP params_json
    """
    as_of_date = processing_date  # engines always receive the resolved processing date
    t = step.task_type

    if t == "ALLOCATION":
        from app.services.allocation_engine import run_allocation
        result = run_allocation(int(step.ref_id), as_of_date, run_by)
        step.ref_run_id = result.id
        step.status = result.status
        step.summary = (
            f"{result.output_row_count or 0} output rows, "
            f"{result.orphan_count or 0} orphans, "
            f"output total {(result.output_total or 0):,.2f}"
        )
        if result.status == "FAILED":
            step.error_message = result.error_message
            raise RuntimeError(result.error_message or "Allocation failed")

    elif t == "ALLOCATION_SP":
        # ── SP-based allocation: calls sp_run_allocation in PostgreSQL ──
        # ref_id = rule_id (integer as string); as_of_date passed automatically.
        from app.services.sp_runner import run_sp
        from app.models.workflow import AllocationRule
        rule_id = int(step.ref_id)
        rule = db.session.get(AllocationRule, rule_id)
        if not rule:
            raise RuntimeError(f"Allocation rule {rule_id} not found")
        params = {
            "p_rule_id":    str(rule_id),
            "p_as_of_date": as_of_date.isoformat(),
            "p_run_by":     run_by,
        }
        sp_run = run_sp(
            sp_name="sp_run_allocation",
            params=params,
            run_by=run_by,
            exec_step_id=step.id,
        )
        step.ref_run_id = sp_run.id
        step.status = sp_run.status
        # Link to the batch_run created by the SP (most recent for this rule+date)
        from app.models.workflow import BatchRun
        batch_run = (
            BatchRun.query
            .filter_by(rule_id=rule_id, as_of_date=as_of_date)
            .order_by(BatchRun.started_at.desc())
            .first()
        )
        step.summary = (
            f"SP allocation: rule={rule.name} | "
            + (f"output={batch_run.output_row_count or 0} rows, "
               f"orphans={batch_run.orphan_count or 0}, "
               f"total={float(batch_run.output_total or 0):,.2f}"
               if batch_run else sp_run.result_message or "completed")
        )
        if sp_run.status == "FAILED":
            step.error_message = sp_run.error_message
            raise RuntimeError(sp_run.error_message or f"sp_run_allocation failed for rule {rule_id}")

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
        from app.services.sp_runner import run_sp, resolve_params
        # Pass original_date so {as_of_date} = form input date;
        # {processing_date} is loaded from DB op vars inside resolve_params.
        params = resolve_params(
            step.params_json or {},
            original_date,
            run_by,
        )
        sp_run = run_sp(
            sp_name=step.ref_id,
            params=params,
            run_by=run_by,
            exec_step_id=step.id,
        )
        step.ref_run_id = sp_run.id
        step.status = sp_run.status  # COMPLETED or FAILED
        step.summary = sp_run.result_message or sp_run.error_message or f"SP '{step.ref_id}' executed"
        if sp_run.status == "FAILED":
            raise RuntimeError(sp_run.error_message or f"Stored procedure '{step.ref_id}' failed")

    else:
        raise ValueError(f"Unknown task_type: {t!r}")
