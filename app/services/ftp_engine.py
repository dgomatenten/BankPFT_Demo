"""Fund Transfer Pricing engine.

Flow:
  FtpProductConfig (DB) → method + rate_code + term + avg_period per product
  RefInterestRate   (DB) → approved rate curve data
  ProcInstData      (DB) → instruments to price; base_rate + cost_of_fund written back

Calculation (MOVING_AVG):
  1. For each instrument in ProcInstData for as_of_date:
     a. Load FtpProductConfig for the instrument's product_code.
     b. Compute lookback window start date from avg_period / avg_period_mult.
     c. Fetch approved RefInterestRate rows matching rate_code + term + term_mult
        whose effective_date falls in [lookback_start, as_of_date].
     d. base_rate = simple average of those rates.
  2. cost_of_fund = balance × base_rate × (actual days in as_of month / actual days in year)
     (actual/actual accrual basis)
"""

import uuid
import calendar
from datetime import timedelta, date
from app.core.time_utils import utc_now

from app.models import db
from app.models.staging import ProcInstData
from app.models.ftp import RefInterestRate, FtpProductConfig, FtpRun


# ──────────────────────────────────────────────────────────────────────────────
# Date helpers
# ──────────────────────────────────────────────────────────────────────────────

def _lookback_start(as_of: date, period: int, mult: str) -> date:
    """Return the start date of the moving-average window."""
    if mult == "D":
        return as_of - timedelta(days=period)
    elif mult == "M":
        month = as_of.month - period
        year = as_of.year
        while month <= 0:
            month += 12
            year -= 1
        last_day = calendar.monthrange(year, month)[1]
        return as_of.replace(year=year, month=month, day=min(as_of.day, last_day))
    elif mult == "Y":
        year = as_of.year - period
        try:
            return as_of.replace(year=year)
        except ValueError:
            # Feb 29 in non-leap year → Feb 28
            return as_of.replace(year=year, day=28)
    # Unknown mult — default to day-based fallback
    return as_of - timedelta(days=period)


# ──────────────────────────────────────────────────────────────────────────────
# Main: run FTP for an as-of date
# ──────────────────────────────────────────────────────────────────────────────

def run_ftp(as_of_date: date, run_by: str) -> FtpRun:
    """
    Calculate base_rate and cost_of_fund for every ProcInstData row on as_of_date.
    Returns the FtpRun record.
    """
    run_id = str(uuid.uuid4())
    ftp_run = FtpRun(
        id=run_id,
        as_of_date=as_of_date,
        status="RUNNING",
        run_by=run_by,
        started_at=utc_now(),
    )
    db.session.add(ftp_run)
    db.session.commit()

    try:
        instruments = ProcInstData.query.filter_by(as_of_date=as_of_date).all()

        # Actual/actual day fraction for as_of_date's month
        days_in_month = calendar.monthrange(as_of_date.year, as_of_date.month)[1]
        days_in_year = 366 if calendar.isleap(as_of_date.year) else 365
        day_fraction = days_in_month / days_in_year

        processed = 0
        matched = 0
        skipped = 0

        for inst in instruments:
            processed += 1

            cfg = FtpProductConfig.query.filter_by(
                product_code=inst.product_code, is_active=True
            ).first()
            if not cfg:
                skipped += 1
                continue

            lookback = _lookback_start(as_of_date, cfg.avg_period, cfg.avg_period_mult)

            rates = RefInterestRate.query.filter(
                RefInterestRate.interest_rate_code == cfg.rate_code,
                RefInterestRate.term == cfg.term,
                RefInterestRate.term_mult == cfg.term_mult,
                RefInterestRate.status == "APPROVED",
                RefInterestRate.effective_date >= lookback,
                RefInterestRate.effective_date <= as_of_date,
            ).all()

            if not rates:
                skipped += 1
                continue

            base_rate = sum(r.rate for r in rates) / len(rates)
            inst.base_rate = base_rate
            inst.cost_of_fund = inst.balance * base_rate * day_fraction
            matched += 1

        db.session.commit()

        ftp_run.instruments_processed = processed
        ftp_run.instruments_matched = matched
        ftp_run.instruments_skipped = skipped
        ftp_run.status = "COMPLETED"
        ftp_run.completed_at = utc_now()
        db.session.commit()

    except Exception as exc:
        ftp_run.status = "FAILED"
        ftp_run.error_message = str(exc)
        ftp_run.completed_at = utc_now()
        db.session.commit()
        raise

    return ftp_run
