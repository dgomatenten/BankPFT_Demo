import os
import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from app.models import db
from app.models.workflow import UploadBatch
from app.models.staging import StgInstData, ProcInstData, StgGlData, ProcGlData
from app.models.allocation import RefStaticAllocation, RefOrgReclass
from app.services.upload_service import allowed_file, process_upload, UPLOAD_CONFIG
from app.services import transition, WorkflowError
from werkzeug.utils import secure_filename

bp = Blueprint("upload", __name__)


@bp.route("/")
def list_uploads():
    uploads = UploadBatch.query.order_by(UploadBatch.created_at.desc()).all()
    return render_template("upload/list.html", uploads=uploads)


@bp.route("/new", methods=["GET", "POST"])
def new_upload():
    if request.method == "POST":
        file = request.files.get("file")
        data_type = request.form.get("data_type", "INSTRUMENT")
        maker_id = request.form.get("maker_id", "user1")

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

    data_types = {k: v for k, v in UPLOAD_CONFIG["data_types"].items()}
    return render_template("upload/new.html", data_types=data_types)


@bp.route("/<batch_id>")
def detail(batch_id):
    batch = UploadBatch.query.get_or_404(batch_id)
    errors = json.loads(batch.errors_json) if batch.errors_json else []

    # Load staged data preview
    preview_rows = []
    preview_cols = []
    if batch.data_type == "INSTRUMENT":
        stg = StgInstData.query.filter_by(upload_batch_id=batch_id).limit(20).all()
        preview_cols = ["account_id", "customer_id", "product_code", "org_unit_id", "balance", "interest_income", "as_of_date"]
        preview_rows = [{c: getattr(r, c) for c in preview_cols} for r in stg]
    elif batch.data_type == "GL":
        stg = StgGlData.query.filter_by(upload_batch_id=batch_id).limit(20).all()
        preview_cols = ["gl_account", "org_unit_id", "debit", "credit", "balance", "as_of_date"]
        preview_rows = [{c: getattr(r, c) for c in preview_cols} for r in stg]
    elif batch.data_type == "ALLOCATION":
        stg = RefStaticAllocation.query.filter_by(upload_batch_id=batch_id).limit(20).all()
        preview_cols = ["allocation_id", "customer_id", "source_org_unit_id", "target_org_unit_id", "ratio", "status"]
        preview_rows = [{c: getattr(r, c) for c in preview_cols} for r in stg]
    elif batch.data_type == "ORG_RECLASS":
        stg = RefOrgReclass.query.filter_by(upload_batch_id=batch_id).limit(20).all()
        preview_cols = ["reclass_id", "source_org_unit_id", "target_org_unit_id", "ratio", "status"]
        preview_rows = [{c: getattr(r, c) for c in preview_cols} for r in stg]

    return render_template("upload/detail.html", batch=batch, errors=errors,
                           preview_cols=preview_cols, preview_rows=preview_rows)


@bp.route("/<batch_id>/action", methods=["POST"])
def action(batch_id):
    batch = UploadBatch.query.get_or_404(batch_id)
    target_status = request.form.get("target_status")
    actor_id = request.form.get("actor_id", "checker1")
    comment = request.form.get("comment", "")

    try:
        transition(batch.status, target_status, batch.maker_id, actor_id)
    except WorkflowError as e:
        flash(str(e), "danger")
        return redirect(url_for("upload.detail", batch_id=batch_id))

    batch.status = target_status
    batch.checker_id = actor_id
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
            ).update({"status": "APPROVED", "checker_id": actor_id})
        elif batch.data_type == "ORG_RECLASS":
            RefOrgReclass.query.filter_by(
                upload_batch_id=batch.id
            ).update({"status": "APPROVED", "checker_id": actor_id})

    db.session.commit()
    flash(f"Batch {target_status.lower()} successfully.", "success")
    return redirect(url_for("upload.detail", batch_id=batch_id))


@bp.route("/<batch_id>/delete", methods=["POST"])
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
    rows = StgInstData.query.filter_by(upload_batch_id=batch_id).all()
    for r in rows:
        db.session.add(ProcInstData(
            upload_batch_id=r.upload_batch_id,
            as_of_date=r.as_of_date,
            account_id=r.account_id,
            customer_id=r.customer_id,
            product_code=r.product_code,
            org_unit_id=r.org_unit_id,
            balance=r.balance,
            interest_income=r.interest_income,
        ))


def _promote_gl(batch_id: str):
    rows = StgGlData.query.filter_by(upload_batch_id=batch_id).all()
    for r in rows:
        db.session.add(ProcGlData(
            upload_batch_id=r.upload_batch_id,
            as_of_date=r.as_of_date,
            gl_account=r.gl_account,
            org_unit_id=r.org_unit_id,
            debit=r.debit,
            credit=r.credit,
            balance=r.balance,
        ))
