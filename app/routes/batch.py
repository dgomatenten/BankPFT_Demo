import os
from datetime import date, datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models.workflow import (
    AllocationRule, BatchRun,
    BatchDefinition, BatchTask, BatchExecution, TASK_TYPES,
)
from app.models.ftp import FtpRun
from app.models import db
from app.services.allocation_engine import run_allocation, BATCH_LOG_DIR
from app.services.ftp_engine import run_ftp
from app.services.batch_executor import run_batch
from app.services.datafile_service import DATAFILE_CONFIG

bp = Blueprint("batch", __name__)


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

    batch = run_allocation(rule_id, as_of, run_by)

    if batch.status == "COMPLETED":
        flash(
            f"Batch completed: {batch.output_row_count} rows generated, "
            f"{batch.orphan_count} orphans. Source total: {batch.source_total:,.2f}, "
            f"Output total: {batch.output_total:,.2f}",
            "success",
        )
    else:
        flash(f"Batch failed: {batch.error_message}", "danger")

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

    ftp_run = run_ftp(as_of, run_by)

    if ftp_run.status == "COMPLETED":
        flash(
            f"FTP run completed: {ftp_run.instruments_matched} matched, "
            f"{ftp_run.instruments_skipped} skipped out of {ftp_run.instruments_processed} instruments.",
            "success",
        )
    else:
        flash(f"FTP run failed: {ftp_run.error_message}", "danger")

    return redirect(url_for("ftp.run_detail", run_id=ftp_run.id))


@bp.route("/<batch_id>")
@login_required
def detail(batch_id):
    batch = BatchRun.query.get_or_404(batch_id)
    log_content = None
    log_path = os.path.join(BATCH_LOG_DIR, f"batch_{batch_id}.log")
    if os.path.exists(log_path):
        with open(log_path, encoding="utf-8") as _f:
            log_content = _f.read()
    return render_template("batch/detail.html", batch=batch, log_content=log_content)


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
    exports = DATAFILE_CONFIG.get("exports", [])
    recent_executions = defn.executions.limit(20).all()
    return render_template(
        "batch/definition_detail.html",
        defn=defn,
        rules=rules,
        formats=formats,
        exports=exports,
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

    if task_type not in TASK_TYPES:
        flash("Invalid task type.", "danger")
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
        execution = run_batch(def_id, as_of, current_user.username)
    except Exception as exc:
        flash(f"Batch failed to start: {exc}", "danger")
        return redirect(url_for("batch.definition_detail", def_id=def_id))

    status_label = {"COMPLETED": "success", "PARTIAL": "warning", "FAILED": "danger"}.get(
        execution.status, "info"
    )
    flash(f"Batch '{defn.name}' finished with status: {execution.status}", status_label)
    return redirect(url_for("batch.execution_detail", exec_id=execution.id))


# ─────────────────────────────────────────────────────────────────────────────
# Execution detail
# ─────────────────────────────────────────────────────────────────────────────

@bp.route("/executions/<exec_id>")
@login_required
def execution_detail(exec_id):
    execution = BatchExecution.query.get_or_404(exec_id)
    return render_template("batch/execution_detail.html", execution=execution)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _auto_label(task_type: str, ref_id: str | None) -> str:
    labels = {
        "ALLOCATION": f"Allocation rule {ref_id}",
        "FTP": "FTP calculation",
        "DATAFILE_IMPORT": f"Import {ref_id}",
        "DATAFILE_EXPORT": f"Export {ref_id}",
        "CUSTOM_SP": f"Custom SP: {ref_id}",
    }
    return labels.get(task_type, task_type)
