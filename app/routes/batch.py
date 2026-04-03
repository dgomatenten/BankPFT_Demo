from datetime import date, datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models.workflow import AllocationRule, BatchRun
from app.models.ftp import FtpRun
from app.services.allocation_engine import run_allocation
from app.services.ftp_engine import run_ftp

bp = Blueprint("batch", __name__)


@bp.route("/")
@login_required
def list_batches():
    batches = BatchRun.query.order_by(BatchRun.started_at.desc()).all()
    rules = AllocationRule.query.filter_by(is_active=True).all()
    ftp_runs = FtpRun.query.order_by(FtpRun.started_at.desc()).limit(30).all()
    return render_template("batch/list.html", batches=batches, rules=rules, ftp_runs=ftp_runs)


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
    return render_template("batch/detail.html", batch=batch)
