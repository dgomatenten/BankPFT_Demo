from datetime import date, datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.models.workflow import AllocationRule, BatchRun
from app.services.allocation_engine import run_allocation

bp = Blueprint("batch", __name__)


@bp.route("/")
def list_batches():
    batches = BatchRun.query.order_by(BatchRun.started_at.desc()).all()
    rules = AllocationRule.query.filter_by(is_active=True).all()
    return render_template("batch/list.html", batches=batches, rules=rules)


@bp.route("/run", methods=["POST"])
def run():
    rule_id = request.form.get("rule_id", type=int)
    as_of_str = request.form.get("as_of_date", "")
    run_by = request.form.get("run_by", "user1")

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


@bp.route("/<batch_id>")
def detail(batch_id):
    batch = BatchRun.query.get_or_404(batch_id)
    return render_template("batch/detail.html", batch=batch)
