from datetime import date, datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import db
from app.models.ftp import RefInterestRate, FtpProductConfig, FtpRun
from app.services.ftp_engine import run_ftp

bp = Blueprint("ftp", __name__)

_MULT_LABELS = {"D": "Day(s)", "M": "Month(s)", "Y": "Year(s)"}


# ── Dashboard ──────────────────────────────────────────────────────────────────

@bp.route("/")
@login_required
def index():
    runs = FtpRun.query.order_by(FtpRun.started_at.desc()).limit(30).all()
    return render_template("ftp/index.html", runs=runs)


@bp.route("/run", methods=["POST"])
@login_required
def run():
    as_of_str = request.form.get("as_of_date", "").strip()
    try:
        as_of = datetime.strptime(as_of_str, "%Y-%m-%d").date() if as_of_str else date.today()
    except ValueError:
        flash("Invalid date format. Use YYYY-MM-DD.", "danger")
        return redirect(url_for("ftp.index"))

    ftp_run = run_ftp(as_of, current_user.username)

    if ftp_run.status == "COMPLETED":
        flash(
            f"FTP run completed: {ftp_run.instruments_matched} instruments priced, "
            f"{ftp_run.instruments_skipped} skipped (no config or no rate data).",
            "success",
        )
    else:
        flash(f"FTP run failed: {ftp_run.error_message}", "danger")

    return redirect(url_for("ftp.run_detail", run_id=ftp_run.id))


@bp.route("/run/<run_id>")
@login_required
def run_detail(run_id):
    ftp_run = FtpRun.query.get_or_404(run_id)
    return render_template("ftp/run_detail.html", run=ftp_run)


# ── FTP Product Config (CRUD) ─────────────────────────────────────────────────

@bp.route("/config")
@login_required
def config_list():
    configs = FtpProductConfig.query.order_by(FtpProductConfig.product_code).all()
    return render_template("ftp/config_list.html", configs=configs, mult_labels=_MULT_LABELS)


@bp.route("/config/new", methods=["GET", "POST"])
@login_required
def config_new():
    if request.method == "POST":
        product_code = request.form.get("product_code", "").strip()
        if not product_code:
            flash("Product code is required.", "danger")
            return redirect(request.url)
        if FtpProductConfig.query.filter_by(product_code=product_code).first():
            flash(f"FTP config for product '{product_code}' already exists.", "danger")
            return redirect(request.url)

        try:
            term = int(request.form.get("term", 1))
            avg_period = int(request.form.get("avg_period", 1))
        except ValueError:
            flash("Term and Average Period must be integers.", "danger")
            return redirect(request.url)

        cfg = FtpProductConfig(
            product_code=product_code,
            method="MOVING_AVG",
            rate_code=request.form.get("rate_code", "").strip(),
            term=term,
            term_mult=request.form.get("term_mult", "M"),
            avg_period=avg_period,
            avg_period_mult=request.form.get("avg_period_mult", "M"),
            is_active="is_active" in request.form,
            created_by=current_user.username,
        )
        db.session.add(cfg)
        db.session.commit()
        flash(f"FTP config for '{product_code}' created.", "success")
        return redirect(url_for("ftp.config_list"))

    # Populate available rate codes from existing approved rates
    rate_codes = db.session.query(RefInterestRate.interest_rate_code).distinct().all()
    rate_codes = [r[0] for r in rate_codes]
    return render_template(
        "ftp/config_form.html", config=None, rate_codes=rate_codes, mult_labels=_MULT_LABELS
    )


@bp.route("/config/<int:cfg_id>/edit", methods=["GET", "POST"])
@login_required
def config_edit(cfg_id):
    cfg = FtpProductConfig.query.get_or_404(cfg_id)

    if request.method == "POST":
        try:
            term = int(request.form.get("term", cfg.term))
            avg_period = int(request.form.get("avg_period", cfg.avg_period))
        except ValueError:
            flash("Term and Average Period must be integers.", "danger")
            return redirect(request.url)

        cfg.rate_code = request.form.get("rate_code", cfg.rate_code).strip()
        cfg.term = term
        cfg.term_mult = request.form.get("term_mult", cfg.term_mult)
        cfg.avg_period = avg_period
        cfg.avg_period_mult = request.form.get("avg_period_mult", cfg.avg_period_mult)
        cfg.is_active = "is_active" in request.form
        db.session.commit()
        flash(f"FTP config for '{cfg.product_code}' updated.", "success")
        return redirect(url_for("ftp.config_list"))

    rate_codes = db.session.query(RefInterestRate.interest_rate_code).distinct().all()
    rate_codes = [r[0] for r in rate_codes]
    return render_template(
        "ftp/config_form.html", config=cfg, rate_codes=rate_codes, mult_labels=_MULT_LABELS
    )


@bp.route("/config/<int:cfg_id>/delete", methods=["POST"])
@login_required
def config_delete(cfg_id):
    cfg = FtpProductConfig.query.get_or_404(cfg_id)
    pc = cfg.product_code
    db.session.delete(cfg)
    db.session.commit()
    flash(f"FTP config for '{pc}' deleted.", "success")
    return redirect(url_for("ftp.config_list"))


# ── Interest Rate browse (upload is via /upload with INTEREST_RATE type) ──────

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

    # Distinct values for filter dropdowns
    all_codes = db.session.query(RefInterestRate.interest_rate_code).distinct().all()
    all_codes = [r[0] for r in all_codes]

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
