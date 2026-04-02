from flask import Blueprint, render_template, flash, redirect, url_for, send_from_directory, current_app
from flask_login import login_required
from app.services.testdata_service import (
    generate_master_data,
    generate_instrument_data,
    generate_allocation_ratios,
    generate_allocation_template_with_data,
    generate_excel_templates,
)
import os

bp = Blueprint("testdata", __name__)


@bp.before_request
@login_required
def require_login():
    pass


@bp.route("/")
def index():
    return render_template("reports/testdata.html")


@bp.route("/generate-master", methods=["POST"])
def gen_master():
    stats = generate_master_data()
    flash(
        f"Generated: {stats['org_units']} Org Units, {stats['products']} Products, "
        f"{stats['customers']} Customers, {stats['accounts']} Accounts",
        "success",
    )
    return redirect(url_for("testdata.index"))


@bp.route("/generate-instruments", methods=["POST"])
def gen_instruments():
    count = generate_instrument_data()
    flash(f"Generated {count} instrument records in proc_inst_data.", "success")
    return redirect(url_for("testdata.index"))


@bp.route("/generate-allocations", methods=["POST"])
def gen_allocations():
    count = generate_allocation_ratios()
    flash(f"Generated {count} allocation ratio records (APPROVED).", "success")
    return redirect(url_for("testdata.index"))


@bp.route("/generate-templates", methods=["POST"])
def gen_templates():
    output_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "templates")
    files = generate_excel_templates(output_dir)
    flash(f"Generated {len(files)} Excel templates in uploads/templates/.", "success")
    return redirect(url_for("testdata.index"))


@bp.route("/generate-alloc-testdata", methods=["POST"])
def gen_alloc_testdata():
    output_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "templates")
    try:
        path, count = generate_allocation_template_with_data(output_dir)
        flash(f"Generated allocation ratio test data: {count} rows in allocation_ratio_testdata.xlsx", "success")
    except ValueError as e:
        flash(str(e), "danger")
    return redirect(url_for("testdata.index"))


@bp.route("/download-template/<filename>")
def download_template(filename):
    template_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "templates")
    return send_from_directory(template_dir, filename, as_attachment=True)
