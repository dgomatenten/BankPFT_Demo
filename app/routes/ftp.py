import json
from datetime import date, datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import db
from app.models.ftp import RefInterestRate, FtpModel, FtpModelRule, FtpProcess, FtpRun
from app.services.ftp_engine import run_ftp

bp = Blueprint("ftp", __name__)

_MULT_LABELS = {"D": "Day(s)", "M": "Month(s)", "Y": "Year(s)"}


# ── Dashboard & Executions ────────────────────────────────────────────────────

@bp.route("/")
@login_required
def index():
    runs = FtpRun.query.order_by(FtpRun.started_at.desc()).limit(30).all()
    processes = FtpProcess.query.filter_by(is_active=True).all()
    return render_template("ftp/index.html", runs=runs, processes=processes)


@bp.route("/run", methods=["POST"])
@login_required
def run():
    process_id = request.form.get("ftp_process_id", type=int)
    as_of_str = request.form.get("as_of_date", "").strip()

    if not process_id:
        flash("You must select an FTP Process to execute.", "danger")
        return redirect(url_for("ftp.index"))

    try:
        as_of = datetime.strptime(as_of_str, "%Y-%m-%d").date() if as_of_str else date.today()
    except ValueError:
        flash("Invalid date format. Use YYYY-MM-DD.", "danger")
        return redirect(url_for("ftp.index"))

    ftp_run = run_ftp(process_id, as_of, current_user.username)

    if ftp_run.status == "COMPLETED":
        flash(
            f"FTP process executed: {ftp_run.instruments_matched} mapped, "
            f"{ftp_run.instruments_skipped} skipped.",
            "success",
        )
    else:
        flash(f"FTP execution failed: {ftp_run.error_message}", "danger")

    return redirect(url_for("ftp.run_detail", run_id=ftp_run.id))


@bp.route("/run/<run_id>")
@login_required
def run_detail(run_id):
    ftp_run = FtpRun.query.get_or_404(run_id)
    return render_template("ftp/run_detail.html", run=ftp_run)


# ── FTP Models ───────────────────────────────────────────────────────────────

@bp.route("/models")
@login_required
def model_list():
    models = FtpModel.query.order_by(FtpModel.model_name).all()
    return render_template("ftp/model_list.html", models=models)


@bp.route("/models/new", methods=["GET", "POST"])
@login_required
def model_new():
    if request.method == "POST":
        name = request.form.get("model_name", "").strip()
        if not name:
            flash("Model name is required.", "danger")
            return redirect(request.url)
            
        model = FtpModel(
            model_name=name,
            description=request.form.get("description", "").strip(),
            is_active="is_active" in request.form,
            created_by=current_user.username
        )
        db.session.add(model)
        db.session.commit()
        flash(f"FTP Model '{name}' created successfully.", "success")
        return redirect(url_for("ftp.model_detail", model_id=model.id))
    
    return render_template("ftp/model_form.html", model=None)


@bp.route("/models/<int:model_id>")
@login_required
def model_detail(model_id):
    model = FtpModel.query.get_or_404(model_id)
    return render_template("ftp/model_detail.html", model=model, mult_labels=_MULT_LABELS)


@bp.route("/models/<int:model_id>/rules/new", methods=["GET", "POST"])
@login_required
def rule_new(model_id):
    model = FtpModel.query.get_or_404(model_id)
    if request.method == "POST":
        product_code = request.form.get("product_code", "").strip()
        component = request.form.get("component", "COF").strip().upper()
        rate_code = request.form.get("rate_code", "").strip()

        if not product_code or not rate_code:
            flash("Product Code and Rate Code are required.", "danger")
            return redirect(request.url)
        if component not in ("COF", "LP", "CLP", "BUF"):
            flash("Component must be COF, LP, CLP, or BUF.", "danger")
            return redirect(request.url)

        rule = FtpModelRule(
            ftp_model_id=model.id,
            product_code=product_code,
            component=component,
            rate_code=rate_code,
            term=int(request.form.get("term", 1)),
            term_mult=request.form.get("term_mult", "M"),
            avg_period=int(request.form.get("avg_period", 1)),
            avg_period_mult=request.form.get("avg_period_mult", "M"),
        )
        db.session.add(rule)
        db.session.commit()
        flash(f"{component} rule configured for {product_code}.", "success")
        return redirect(url_for("ftp.model_detail", model_id=model.id))

    rate_codes = [r[0] for r in db.session.query(RefInterestRate.interest_rate_code).distinct().all()]
    return render_template("ftp/rule_form.html", model=model, rate_codes=rate_codes, mult_labels=_MULT_LABELS)


# ── FTP Processes ────────────────────────────────────────────────────────────

@bp.route("/processes")
@login_required
def process_list():
    processes = FtpProcess.query.order_by(FtpProcess.process_name).all()
    return render_template("ftp/process_list.html", processes=processes)


@bp.route("/processes/new", methods=["GET", "POST"])
@login_required
def process_new():
    if request.method == "POST":
        process_name = request.form.get("process_name", "").strip()
        model_id = request.form.get("ftp_model_id", type=int)

        if not process_name or not model_id:
            flash("Process Name and Model selection are required.", "danger")
            return redirect(request.url)

        proc = FtpProcess(
            process_name=process_name,
            description=request.form.get("description", "").strip(),
            ftp_model_id=model_id,
            target_table=request.form.get("target_table", "stg_inst_data"),
            is_active="is_active" in request.form,
            created_by=current_user.username
        )
        db.session.add(proc)
        db.session.commit()
        flash(f"Process '{process_name}' registered successfully.", "success")
        return redirect(url_for("ftp.process_list"))
        
    models = FtpModel.query.filter_by(is_active=True).all()
    return render_template("ftp/process_form.html", process=None, models=models)


# ── Interest Rates ──────────────────────────────────────────────────────────

@bp.route("/rates")
@login_required
def rates_list():
    rate_code = request.args.get("rate_code", "")
    term_filter = request.args.get("term", "")
    term_mult_filter = request.args.get("term_mult", "")
    status_filter = request.args.get("status", "APPROVED")

    q = RefInterestRate.query
    if rate_code:
        q = q.filter(RefInterestRate.interest_rate_code == rate_code)
    if term_filter:
        try:
            q = q.filter(RefInterestRate.term == int(term_filter))
        except ValueError:
            pass
    if term_mult_filter:
        q = q.filter(RefInterestRate.term_mult == term_mult_filter)
    if status_filter:
        q = q.filter(RefInterestRate.status == status_filter)

    rates = q.order_by(
        RefInterestRate.interest_rate_code,
        RefInterestRate.term_mult,
        RefInterestRate.term,
        RefInterestRate.effective_date.desc(),
    ).limit(500).all()

    all_codes = [r[0] for r in db.session.query(RefInterestRate.interest_rate_code).distinct().all()]

    return render_template(
        "ftp/rates_list.html",
        rates=rates,
        all_codes=all_codes,
        rate_code=rate_code,
        term_filter=term_filter,
        term_mult_filter=term_mult_filter,
        status_filter=status_filter,
        mult_labels=_MULT_LABELS,
    )
