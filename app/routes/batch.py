import os
import json
from datetime import datetime, date
from threading import Thread
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from app.models.workflow import (
    AllocationRule, BatchRun,
    BatchDefinition, BatchTask, BatchExecution, TASK_TYPES, SpRun, RegisteredSp
)
from app.models.ftp import FtpRun
from app.models import db
from app.services.allocation_engine import prepare_allocation, run_allocation_async, BATCH_LOG_DIR
from app.services.ftp_engine import prepare_ftp, run_ftp_async
from app.services.batch_executor import prepare_batch, run_batch_async
from app.services.datafile_service import DATAFILE_CONFIG

from app.models.datafile import DataFileBatch

bp = Blueprint("batch", __name__)


@bp.route("/api/run-by-name", methods=["POST"])
def api_run_by_name():
    """REST API endpoint to run a batch definition by name."""
    data = request.get_json() or {}
    batch_name = data.get("name")
    if not batch_name:
        return {"error": "Batch 'name' is required in JSON payload"}, 400
        
    defn = BatchDefinition.query.filter_by(name=batch_name).first()
    if not defn:
        return {"error": f"Batch definition '{batch_name}' not found"}, 404
        
    as_of_str = data.get("as_of_date", "")
    try:
        as_of = datetime.strptime(as_of_str, "%Y-%m-%d").date() if as_of_str else date.today()
    except ValueError:
        return {"error": "Invalid date. Use YYYY-MM-DD."}, 400

    run_by = data.get("run_by", "api_user")
    
    if not defn.tasks:
        return {"error": "This batch has no steps. Add at least one task first."}, 400

    try:
        execution = prepare_batch(defn.id, as_of, run_by)
        app = current_app._get_current_object()
        Thread(target=run_batch_async, args=(app, execution.id, as_of, run_by)).start()
    except Exception as exc:
        return {"error": f"Batch failed to start: {exc}"}, 500

    return {
        "status": "RUNNING", 
        "execution_id": execution.id, 
        "message": f"Batch '{defn.name}' started in background."
    }


@bp.route("/monitor")
@login_required
def monitor():
    """Live dashboard showing running and recent batch activity across all engine types."""
    from flask import jsonify as _jf

    running_executions = BatchExecution.query.filter(
        BatchExecution.status == "RUNNING"
    ).order_by(BatchExecution.started_at.desc()).all()

    running_alloc = BatchRun.query.filter(
        BatchRun.status == "RUNNING"
    ).order_by(BatchRun.started_at.desc()).all()

    recent_executions = BatchExecution.query.filter(
        BatchExecution.status != "RUNNING"
    ).order_by(BatchExecution.started_at.desc()).limit(20).all()

    recent_alloc = BatchRun.query.filter(
        BatchRun.status != "RUNNING"
    ).order_by(BatchRun.started_at.desc()).limit(20).all()

    recent_ftp = FtpRun.query.order_by(FtpRun.started_at.desc()).limit(20).all()

    recent_datafile = DataFileBatch.query.order_by(
        DataFileBatch.started_at.desc()
    ).limit(20).all()

    recent_sp = SpRun.query.order_by(SpRun.started_at.desc()).limit(20).all()

    return render_template(
        "batch/monitor.html",
        running_executions=running_executions,
        running_alloc=running_alloc,
        recent_executions=recent_executions,
        recent_alloc=recent_alloc,
        recent_ftp=recent_ftp,
        recent_datafile=recent_datafile,
        recent_sp=recent_sp,
    )


@bp.route("/monitor/status")
@login_required
def monitor_status():
    """JSON endpoint polled by the monitor page for live refresh."""
    from flask import jsonify

    running_exec_count = BatchExecution.query.filter_by(status="RUNNING").count()
    running_alloc_count = BatchRun.query.filter_by(status="RUNNING").count()
    total_running = running_exec_count + running_alloc_count

    return jsonify({
        "running_total": total_running,
        "running_executions": running_exec_count,
        "running_allocations": running_alloc_count,
    })


@bp.route("/")
@login_required
def list_batches():
    definitions  = BatchDefinition.query.filter_by(is_active=True).order_by(BatchDefinition.name).all()
    executions   = BatchExecution.query.order_by(BatchExecution.started_at.desc()).limit(30).all()
    # kept for the advanced / legacy single-engine panel
    rules        = AllocationRule.query.filter_by(is_active=True).all()
    ftp_runs     = FtpRun.query.order_by(FtpRun.started_at.desc()).limit(10).all()
    return render_template(
        "batch/list.html",
        definitions=definitions,
        executions=executions,
        rules=rules,
        ftp_runs=ftp_runs,
    )


@bp.route("/run", methods=["POST"])
@login_required
def run():
    rule_id = request.form.get("rule_id", type=int)
    as_of_str = request.form.get("as_of_date", "")
    run_by = current_user.username

    if not rule_id:
        flash("Please select a rule.", "danger")
        return redirect(url_for("batch.list_batches"))

    try:
        as_of = datetime.strptime(as_of_str, "%Y-%m-%d").date() if as_of_str else date.today()
    except ValueError:
        flash("Invalid date format. Use YYYY-MM-DD.", "danger")
        return redirect(url_for("batch.list_batches"))

    batch = prepare_allocation(rule_id, as_of, run_by)
    app = current_app._get_current_object()
    Thread(target=run_allocation_async, args=(app, batch.id)).start()

    flash(f"Allocation rule run started in background.", "info")
    return redirect(url_for("batch.detail", batch_id=batch.id))


@bp.route("/run-ftp", methods=["POST"])
@login_required
def run_ftp_batch():
    as_of_str = request.form.get("as_of_date", "")
    run_by = current_user.username

    try:
        as_of = datetime.strptime(as_of_str, "%Y-%m-%d").date() if as_of_str else date.today()
    except ValueError:
        flash("Invalid date format. Use YYYY-MM-DD.", "danger")
        return redirect(url_for("batch.list_batches"))

    # Select the first FtpProcess for the 'Run FTP' button if not specified
    # Actually, we should probably handle this better. 
    # For now, we assume process_id 1 or look it up.
    from app.models.ftp import FtpProcess
    proc = FtpProcess.query.first()
    if not proc:
        flash("No FTP processes configured.", "danger")
        return redirect(url_for("batch.list_batches"))

    ftp_run = prepare_ftp(proc.id, as_of, run_by)
    app = current_app._get_current_object()
    Thread(target=run_ftp_async, args=(app, ftp_run.id)).start()

    flash(f"FTP calculation started in background.", "info")
    return redirect(url_for("ftp.run_detail", run_id=ftp_run.id))


@bp.route("/<batch_id>")
@login_required
def detail(batch_id):
    batch = BatchRun.query.get_or_404(batch_id)
    log_content = None
    log_path = os.path.join(BATCH_LOG_DIR, f"batch_{batch_id}.log")
    log_exists = os.path.exists(log_path)
    if log_exists:
        with open(log_path, encoding="utf-8") as _f:
            log_content = _f.read()
    else:
        log_content = f"DEBUG INFO:\nExpected Path: {log_path}\nExists: {log_exists}\nbatch_id: '{batch_id}'\nLength of ID: {len(batch_id)}"
        
    return render_template("batch/detail.html", batch=batch, log_content=log_content)


@bp.route("/runs/<batch_id>/status")
@login_required
def batch_run_status(batch_id):
    """JSON endpoint for polling an individual allocation run status."""
    from flask import jsonify
    batch = BatchRun.query.get_or_404(batch_id)
    return jsonify({
        "id": batch.id,
        "status": batch.status,
        "source_row_count": batch.source_row_count,
        "output_row_count": batch.output_row_count,
        "orphan_count": batch.orphan_count,
        "source_total": float(batch.source_total or 0),
        "output_total": float(batch.output_total or 0),
        "error_message": batch.error_message,
        "completed_at": batch.completed_at.isoformat() if batch.completed_at else None,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Batch Definitions — define multi-task batches
# ─────────────────────────────────────────────────────────────────────────────

@bp.route("/definitions")
@login_required
def list_definitions():
    definitions = BatchDefinition.query.order_by(BatchDefinition.name).all()
    return render_template("batch/definitions.html", definitions=definitions)


@bp.route("/definitions/new", methods=["GET", "POST"])
@login_required
def new_definition():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        continue_on_error = request.form.get("continue_on_error") == "1"
        if not name:
            flash("Name is required.", "danger")
            return redirect(url_for("batch.new_definition"))
        if BatchDefinition.query.filter_by(name=name).first():
            flash(f"A batch definition named '{name}' already exists.", "danger")
            return redirect(url_for("batch.new_definition"))
        defn = BatchDefinition(
            name=name,
            description=description or None,
            continue_on_error=continue_on_error,
            created_by=current_user.username,
        )
        db.session.add(defn)
        db.session.commit()
        flash(f"Batch definition '{name}' created.", "success")
        return redirect(url_for("batch.definition_detail", def_id=defn.id))
    return render_template("batch/definition_new.html")


@bp.route("/definitions/<int:def_id>")
@login_required
def definition_detail(def_id):
    defn = BatchDefinition.query.get_or_404(def_id)
    rules = AllocationRule.query.filter_by(is_active=True).order_by(AllocationRule.name).all()
    formats = DATAFILE_CONFIG.get("formats", [])
    exports = [e for e in DATAFILE_CONFIG.get("formats", []) if e.get("type") == "EXPORT"]
    
    from app.models.workflow import RegisteredSp
    from app.models.ftp import FtpProcess
    registered_sps = RegisteredSp.query.filter_by(is_batch_enabled=True).order_by(RegisteredSp.procedure_name).all()
    ftp_processes = FtpProcess.query.filter_by(is_active=True).all()
    
    task_types = [
        "ALLOCATION",
        "ALLOCATION_SP",
        "FTP",
        "DATAFILE_IMPORT",
        "DATAFILE_EXPORT",
        "CUSTOM_SP"
    ]
    recent_executions = BatchExecution.query.filter_by(definition_id=def_id).order_by(
        BatchExecution.started_at.desc()
    ).limit(10).all()

    return render_template(
        "batch/definition_detail.html",
        defn=defn,
        rules=rules,
        formats=formats,
        exports=exports,
        registered_sps=registered_sps,
        task_types=TASK_TYPES,
        recent_executions=recent_executions,
    )


@bp.route("/definitions/<int:def_id>/tasks/add", methods=["POST"])
@login_required
def add_task(def_id):
    defn = BatchDefinition.query.get_or_404(def_id)
    task_type = request.form.get("task_type", "").strip()
    ref_id = request.form.get("ref_id", "").strip() or None
    label = request.form.get("label", "").strip() or None
    params_raw = request.form.get("params_json", "").strip()

    if task_type not in TASK_TYPES:
        flash("Invalid task type.", "danger")
        return redirect(url_for("batch.definition_detail", def_id=def_id))

    # Parse optional params JSON for CUSTOM_SP
    params_json = None
    if task_type == "CUSTOM_SP" and params_raw:
        try:
            params_json = json.loads(params_raw)
            if not isinstance(params_json, dict):
                raise ValueError("params_json must be a JSON object")
        except (ValueError, json.JSONDecodeError) as e:
            flash(f"Invalid params JSON: {e}", "danger")
            return redirect(url_for("batch.definition_detail", def_id=def_id))

    # Auto-generate label if blank
    if not label:
        label = _auto_label(task_type, ref_id)

    # Auto-assign next step_order
    existing = [t.step_order for t in defn.tasks]
    next_order = (max(existing) + 1) if existing else 1

    task = BatchTask(
        definition_id=def_id,
        step_order=next_order,
        task_type=task_type,
        ref_id=ref_id,
        label=label,
        params_json=params_json,
    )
    db.session.add(task)
    db.session.commit()
    flash(f"Step {next_order}: {label} added.", "success")
    return redirect(url_for("batch.definition_detail", def_id=def_id))


@bp.route("/definitions/<int:def_id>/tasks/<int:task_id>/remove", methods=["POST"])
@login_required
def remove_task(def_id, task_id):
    task = BatchTask.query.filter_by(id=task_id, definition_id=def_id).first_or_404()
    db.session.delete(task)
    db.session.commit()
    # Re-sequence remaining tasks
    for i, t in enumerate(
        BatchTask.query.filter_by(definition_id=def_id).order_by(BatchTask.step_order).all(), 1
    ):
        t.step_order = i
    db.session.commit()
    flash("Step removed.", "success")
    return redirect(url_for("batch.definition_detail", def_id=def_id))


@bp.route("/definitions/<int:def_id>/run", methods=["POST"])
@login_required
def run_definition(def_id):
    defn = BatchDefinition.query.get_or_404(def_id)
    as_of_str = request.form.get("as_of_date", "")
    try:
        as_of = datetime.strptime(as_of_str, "%Y-%m-%d").date() if as_of_str else date.today()
    except ValueError:
        flash("Invalid date. Use YYYY-MM-DD.", "danger")
        return redirect(url_for("batch.definition_detail", def_id=def_id))

    if not defn.tasks:
        flash("This batch has no steps. Add at least one task first.", "warning")
        return redirect(url_for("batch.definition_detail", def_id=def_id))

    try:
        execution = prepare_batch(def_id, as_of, current_user.username)
        app = current_app._get_current_object()
        Thread(target=run_batch_async, args=(app, execution.id, as_of, current_user.username)).start()
    except Exception as exc:
        flash(f"Batch failed to start: {exc}", "danger")
        return redirect(url_for("batch.definition_detail", def_id=def_id))

    flash(f"Batch '{defn.name}' started in background.", "info")
    return redirect(url_for("batch.execution_detail", exec_id=execution.id))


# ─────────────────────────────────────────────────────────────────────────────
# Execution detail
# ─────────────────────────────────────────────────────────────────────────────

@bp.route("/executions/<exec_id>")
@login_required
def execution_detail(exec_id):
    execution = BatchExecution.query.get_or_404(exec_id)
    log_content = None
    log_path = os.path.join(BATCH_LOG_DIR, f"batch_execution_{exec_id}.log")
    if os.path.exists(log_path):
        with open(log_path, encoding="utf-8") as _f:
            log_content = _f.read()
    return render_template("batch/execution_detail.html", execution=execution, log_content=log_content)


@bp.route("/executions/<exec_id>/status")
@login_required
def execution_status(exec_id):
    """JSON endpoint for polling execution status from the browser."""
    from flask import jsonify
    execution = BatchExecution.query.get_or_404(exec_id)
    return jsonify({
        "id": execution.id,
        "status": execution.status,
        "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
        "steps": [
            {
                "order": s.step_order,
                "status": s.status,
                "summary": s.summary,
                "error": s.error_message,
                "ref_run_id": s.ref_run_id,
            } for s in execution.steps
        ]
    })


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _auto_label(task_type: str, ref_id: str | None) -> str:
    labels = {
        "ALLOCATION":    f"Allocation rule {ref_id}",
        "ALLOCATION_SP": f"Allocation SP: rule {ref_id}",
        "FTP": "FTP calculation",
        "DATAFILE_IMPORT": f"Import {ref_id}",
        "DATAFILE_EXPORT": f"Export {ref_id}",
        "CUSTOM_SP": f"Custom SP: {ref_id}",
    }
    return labels.get(task_type, task_type)


# ─────────────────────────────────────────────────────────────────────────────
# SP Run detail — drill-down from a batch execution step
# ─────────────────────────────────────────────────────────────────────────────

@bp.route("/sp-runs/<run_id>")
@login_required
def sp_detail(run_id):
    sp_run = SpRun.query.get_or_404(run_id)
    # Resolve back link: if launched from a batch step, go to that execution
    from app.models.workflow import BatchExecutionStep
    parent_execution_id = None
    if sp_run.exec_step_id:
        step = db.session.get(BatchExecutionStep, sp_run.exec_step_id)
        if step:
            parent_execution_id = step.execution_id
    return render_template(
        "batch/sp_detail.html",
        sp_run=sp_run,
        parent_execution_id=parent_execution_id,
    )


@bp.route("/sp-runs/<run_id>/status")
@login_required
def sp_status(run_id):
    """JSON endpoint for polling SP run status from the browser."""
    from flask import jsonify
    sp_run = SpRun.query.get_or_404(run_id)
    return jsonify({
        "id": sp_run.id,
        "status": sp_run.status,
        "completed_at": sp_run.completed_at.isoformat() if sp_run.completed_at else None,
        "result_message": sp_run.result_message,
        "error_message": sp_run.error_message,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Stored Procedures Registry
# ─────────────────────────────────────────────────────────────────────────────

@bp.route("/procedures")
@login_required
def list_procedures():
    procedures = RegisteredSp.query.order_by(RegisteredSp.procedure_name).all()
    
    # Fetch all actual procedures from the DB to populate the Add dropdown
    query = db.text("""
        SELECT routine_schema, routine_name
        FROM information_schema.routines
        WHERE routine_type = 'PROCEDURE' 
          AND routine_schema NOT IN ('pg_catalog', 'information_schema');
    """)
    db_result = db.session.execute(query).fetchall()
    db_procedures = [f"{row[0]}.{row[1]}" for row in db_result]
    
    return render_template("batch/procedures.html", procedures=procedures, db_procedures=db_procedures)


@bp.route("/procedures/add", methods=["POST"])
@login_required
def add_procedure():
    name = request.form.get("procedure_name", "").strip()
    description = request.form.get("description", "").strip()
    if not name:
        flash("Procedure name is required.", "danger")
        return redirect(url_for("batch.list_procedures"))
        
    if RegisteredSp.query.filter_by(procedure_name=name).first():
        flash("This procedure is already registered.", "warning")
        return redirect(url_for("batch.list_procedures"))
        
    sp = RegisteredSp(
        procedure_name=name,
        description=description,
        is_batch_enabled=True
    )
    db.session.add(sp)
    db.session.commit()
    flash(f"Registered stored procedure '{name}'.", "success")
    return redirect(url_for("batch.list_procedures"))


@bp.route("/procedures/<int:sp_id>/toggle", methods=["POST"])
@login_required
def toggle_procedure(sp_id):
    sp = RegisteredSp.query.get_or_404(sp_id)
    sp.is_batch_enabled = not sp.is_batch_enabled
    db.session.commit()
    state = "enabled" if sp.is_batch_enabled else "disabled"
    flash(f"Stored procedure '{sp.procedure_name}' is now {state}.", "info")
    return redirect(url_for("batch.list_procedures"))
