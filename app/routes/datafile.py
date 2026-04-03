import json
import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required, current_user
from app.models.datafile import DataFileBatch
from app.services.datafile_service import (
    DATAFILE_CONFIG, OUTBOX_DIR, list_inbox_files, import_file, export_data
)

bp = Blueprint("datafile", __name__)


@bp.route("/")
@login_required
def index():
    inbox = list_inbox_files()
    history = DataFileBatch.query.order_by(DataFileBatch.started_at.desc()).limit(50).all()
    formats = DATAFILE_CONFIG.get("formats", [])
    exports = DATAFILE_CONFIG.get("exports", [])
    return render_template(
        "datafile/index.html",
        inbox=inbox,
        history=history,
        formats=formats,
        exports=exports,
    )


@bp.route("/import", methods=["POST"])
@login_required
def run_import():
    format_id = request.form.get("format_id", "").strip()
    filename = request.form.get("filename", "").strip()

    # Validate filename — must not contain path traversal characters
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        flash("Invalid filename.", "danger")
        return redirect(url_for("datafile.index"))

    if not format_id:
        flash("Please select a file format.", "danger")
        return redirect(url_for("datafile.index"))

    try:
        batch = import_file(format_id, filename, current_user.username)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("datafile.index"))

    if batch.status == "COMPLETED":
        msg = f"Import completed: {batch.row_count:,} rows loaded into '{batch.target_table}'."
        if batch.error_count:
            msg += f" {batch.error_count} row-level errors."
        flash(msg, "success" if not batch.error_count else "warning")
    else:
        flash(f"Import failed: {batch.error_message}", "danger")

    return redirect(url_for("datafile.batch_detail", batch_id=batch.id))


@bp.route("/export", methods=["POST"])
@login_required
def run_export():
    export_id = request.form.get("export_id", "").strip()
    as_of_date = request.form.get("as_of_date", "").strip() or None

    if not export_id:
        flash("Please select an export configuration.", "danger")
        return redirect(url_for("datafile.index"))

    try:
        batch = export_data(export_id, current_user.username, as_of_date)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("datafile.index"))

    if batch.status == "COMPLETED":
        flash(f"Export completed: {batch.row_count:,} rows written to '{batch.filename}'.", "success")
    else:
        flash(f"Export failed: {batch.error_message}", "danger")

    return redirect(url_for("datafile.batch_detail", batch_id=batch.id))


@bp.route("/download/<batch_id>")
@login_required
def download(batch_id):
    batch = DataFileBatch.query.get_or_404(batch_id)
    if batch.operation != "EXPORT" or batch.status != "COMPLETED":
        flash("File not available for download.", "warning")
        return redirect(url_for("datafile.index"))

    filepath = os.path.join(OUTBOX_DIR, batch.filename)
    if not os.path.exists(filepath):
        flash("Output file not found on disk.", "danger")
        return redirect(url_for("datafile.index"))

    return send_file(filepath, as_attachment=True, download_name=batch.filename)


@bp.route("/batch/<batch_id>")
@login_required
def batch_detail(batch_id):
    batch = DataFileBatch.query.get_or_404(batch_id)
    errors = json.loads(batch.errors_json) if batch.errors_json else []
    return render_template("datafile/batch_detail.html", batch=batch, errors=errors)
