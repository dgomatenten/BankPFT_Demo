from flask import Blueprint, render_template
from flask_login import login_required
from app.models.workflow import UploadBatch, AllocationRule, BatchRun
from app.models.allocation import FctMgmtLedger

bp = Blueprint("dashboard", __name__)


@bp.route("/")
@login_required
def index():
    uploads = UploadBatch.query.order_by(UploadBatch.created_at.desc()).limit(10).all()
    rules = AllocationRule.query.order_by(AllocationRule.created_at.desc()).limit(10).all()
    batches = BatchRun.query.order_by(BatchRun.started_at.desc()).limit(10).all()
    ledger_count = FctMgmtLedger.query.count()
    return render_template(
        "dashboard/index.html",
        uploads=uploads,
        rules=rules,
        batches=batches,
        ledger_count=ledger_count,
    )
