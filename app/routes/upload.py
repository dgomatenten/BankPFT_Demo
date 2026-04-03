import os
import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from sqlalchemy import text
from app.models import db
from app.models.workflow import UploadBatch
from app.models.staging import StgInstData, StgGlData
from app.models.allocation import RefStaticAllocation, RefOrgReclass
from app.services.upload_service import allowed_file, process_upload, UPLOAD_CONFIG
from app.services import transition, WorkflowError
from werkzeug.utils import secure_filename

bp = Blueprint("upload", __name__)


@bp.route("/")
@login_required
def list_uploads():
    uploads = UploadBatch.query.order_by(UploadBatch.created_at.desc()).all()
    return render_template("upload/list.html", uploads=uploads)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new_upload():
    if request.method == "POST":
        file = request.files.get("file")
        data_type = request.form.get("data_type", "INSTRUMENT")
        maker_id = current_user.username

        if not file or file.filename == "":
            flash("No file selected.", "danger")
            return redirect(request.url)

        if not allowed_file(file.filename):
            flash("Only .xlsx and .csv files are allowed.", "danger")
            return redirect(request.url)

        filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        batch = process_upload(filepath, data_type, maker_id)
        if batch.error_count > 0:
            flash(f"Upload has {batch.error_count} validation errors. Fix and re-upload.", "warning")
        else:
            flash(f"Upload successful — {batch.row_count} rows staged. Status: {batch.status}", "success")

        return redirect(url_for("upload.detail", batch_id=batch.id))

    data_types = UPLOAD_CONFIG["data_types"]
    return render_template("upload/new.html", data_types=data_types)


@bp.route("/<batch_id>")
@login_required
def detail(batch_id):
    batch = UploadBatch.query.get_or_404(batch_id)
    errors = json.loads(batch.errors_json) if batch.errors_json else []

    # Load staged data preview — derive columns from upload_config.json
    preview_rows = []
    preview_cols = []
    _PREVIEW_MODELS = {
        "INSTRUMENT": (StgInstData, []),
        "GL": (StgGlData, []),
        "ALLOCATION": (RefStaticAllocation, ["status"]),
        "ORG_RECLASS": (RefOrgReclass, ["status"]),
    }
    type_cfg = UPLOAD_CONFIG["data_types"].get(batch.data_type, {})
    preview_info = _PREVIEW_MODELS.get(batch.data_type)
    if preview_info:
        model_cls, extra_cols = preview_info
        preview_cols = list(type_cfg.get("column_mapping", {}).keys()) + extra_cols
        stg = model_cls.query.filter_by(upload_batch_id=batch_id).limit(20).all()
        preview_rows = [{c: getattr(r, c, None) for c in preview_cols} for r in stg]

    return render_template("upload/detail.html", batch=batch, errors=errors,
                           preview_cols=preview_cols, preview_rows=preview_rows)


@bp.route("/<batch_id>/action", methods=["POST"])
@login_required
def action(batch_id):
    batch = UploadBatch.query.get_or_404(batch_id)
    target_status = request.form.get("target_status")
    comment = request.form.get("comment", "")

    try:
        transition(batch.status, target_status, batch.maker_id, current_user)
    except WorkflowError as e:
        flash(str(e), "danger")
        return redirect(url_for("upload.detail", batch_id=batch_id))

    batch.status = target_status
    batch.checker_id = current_user.username
    batch.checker_comment = comment

    # On APPROVED, promote staging -> processing
    if target_status == "APPROVED":
        if batch.data_type == "INSTRUMENT":
            _promote_instrument(batch.id)
        elif batch.data_type == "GL":
            _promote_gl(batch.id)
        elif batch.data_type == "ALLOCATION":
            RefStaticAllocation.query.filter_by(
                upload_batch_id=batch.id
            ).update({"status": "APPROVED", "checker_id": current_user.username})
        elif batch.data_type == "ORG_RECLASS":
            RefOrgReclass.query.filter_by(
                upload_batch_id=batch.id
            ).update({"status": "APPROVED", "checker_id": current_user.username})

    db.session.commit()
    flash(f"Batch {target_status.lower()} successfully.", "success")
    return redirect(url_for("upload.detail", batch_id=batch_id))


@bp.route("/<batch_id>/delete", methods=["POST"])
@login_required
def delete(batch_id):
    batch = UploadBatch.query.get_or_404(batch_id)
    if batch.status not in ("DRAFT", "REJECTED"):
        flash("Only DRAFT or REJECTED uploads can be deleted.", "danger")
        return redirect(url_for("upload.detail", batch_id=batch_id))

    # Clean up staged data
    StgInstData.query.filter_by(upload_batch_id=batch_id).delete()
    StgGlData.query.filter_by(upload_batch_id=batch_id).delete()
    RefStaticAllocation.query.filter_by(upload_batch_id=batch_id).delete()
    RefOrgReclass.query.filter_by(upload_batch_id=batch_id).delete()

    db.session.delete(batch)
    db.session.commit()
    flash("Upload batch deleted.", "success")
    return redirect(url_for("upload.list_uploads"))


def _promote_instrument(batch_id: str):
    db.session.execute(text(
        "INSERT INTO proc_inst_data "
        "(upload_batch_id, as_of_date, account_id, customer_id, product_code, org_unit_id, balance, interest_income) "
        "SELECT upload_batch_id, as_of_date, account_id, customer_id, product_code, org_unit_id, balance, interest_income "
        "FROM stg_inst_data WHERE upload_batch_id = :batch_id"
    ), {"batch_id": batch_id})


def _promote_gl(batch_id: str):
    db.session.execute(text(
        "INSERT INTO proc_gl_data "
        "(upload_batch_id, as_of_date, gl_account, org_unit_id, debit, credit, balance) "
        "SELECT upload_batch_id, as_of_date, gl_account, org_unit_id, debit, credit, balance "
        "FROM stg_gl_data WHERE upload_batch_id = :batch_id"
    ), {"batch_id": batch_id})
