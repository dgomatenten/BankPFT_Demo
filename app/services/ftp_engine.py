"""Fund Transfer Pricing engine.

Flow:
  FtpProcess  (DB) → identifies the FtpModel and target table
  FtpModelRule (DB) → one rule per component (COF / LP / CLP) per product
  RefInterestRate (DB) → approved rate curve data (each component has its own rate_code)
  ProcInstData / StgInstData → instruments to price; FTP columns written back

Calculation (MOVING_AVG) — per component:
  1. Build rule_map: { product_code: { component: rule } }
  2. For each instrument:
     a. Look up COF rule → moving avg of ref_interest_rate → writes base_rate, cost_of_fund
     b. Look up LP  rule → moving avg of ref_interest_rate → writes lp_rate,   lp_amount
     c. Look up CLP rule → moving avg of ref_interest_rate → writes clp_rate,  clp_amount
  3. All three outputs are independent; missing rules simply skip that component.
"""

import uuid
import calendar
from decimal import Decimal
from datetime import timedelta, date
from app.core.time_utils import utc_now

from app.models import db
from app.models.staging import ProcInstData, StgInstData
from app.models.ftp import RefInterestRate, FtpModelRule, FtpProcess, FtpRun

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
            return as_of.replace(year=year, day=28)
    return as_of - timedelta(days=period)


def _moving_avg_rate(rule: FtpModelRule, as_of: date):
    """Return the moving-average rate for a rule, or None if no approved rates found."""
    lookback = _lookback_start(as_of, rule.avg_period, rule.avg_period_mult)
    rates = RefInterestRate.query.filter(
        RefInterestRate.interest_rate_code == rule.rate_code,
        RefInterestRate.term == rule.term,
        RefInterestRate.term_mult == rule.term_mult,
        RefInterestRate.status == "APPROVED",
        RefInterestRate.effective_date >= lookback,
        RefInterestRate.effective_date <= as_of,
    ).all()
    if not rates:
        return None
    return sum(r.rate for r in rates) / len(rates)


# ──────────────────────────────────────────────────────────────────────────────
# Main: run FTP for an as-of date mapped securely to an FTP Process
# ──────────────────────────────────────────────────────────────────────────────

def run_ftp(ftp_process_id: int, as_of_date: date, run_by: str) -> FtpRun:
    """
    Calculate COF, LP, and CLP components for all instruments on as_of_date,
    using the FtpModel rules bound to the given FtpProcess.

    Each component is driven by its own dedicated FtpModelRule with its own
    rate_code, term, and moving-average window.
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
        process = FtpProcess.query.get(ftp_process_id)
        if not process:
            raise ValueError(f"FTP Process {ftp_process_id} not found.")

        # Dynamically map the target SQLAlchemy model
        TargetModel = StgInstData if process.target_table == 'stg_inst_data' else ProcInstData
        instruments = TargetModel.query.filter_by(as_of_date=as_of_date).all()

        days_in_month = calendar.monthrange(as_of_date.year, as_of_date.month)[1]
        days_in_year = 366 if calendar.isleap(as_of_date.year) else 365
        day_fraction = Decimal(days_in_month) / Decimal(days_in_year)

        processed = 0
        matched = 0
        skipped = 0

        # Build component-aware rule map: { product_code: { component: rule } }
        all_rules = FtpModelRule.query.filter_by(ftp_model_id=process.ftp_model_id).all()
        rule_map: dict[str, dict[str, FtpModelRule]] = {}
        for r in all_rules:
            rule_map.setdefault(r.product_code, {})[r.component] = r

        for inst in instruments:
            processed += 1
            components = rule_map.get(inst.product_code)

            if not components:
                skipped += 1
                continue

            inst_matched = False

            # ── COF ──────────────────────────────────────────────────────────
            cof_rule = components.get("COF")
            if cof_rule:
                base_rate = _moving_avg_rate(cof_rule, as_of_date)
                if base_rate is not None:
                    if hasattr(inst, 'base_rate'):
                        inst.base_rate = base_rate
                    if hasattr(inst, 'cost_of_fund'):
                        inst.cost_of_fund = inst.balance * base_rate * day_fraction
                    inst_matched = True

            # ── LP ───────────────────────────────────────────────────────────
            lp_rule = components.get("LP")
            if lp_rule:
                lp_rate = _moving_avg_rate(lp_rule, as_of_date)
                if lp_rate is not None:
                    if hasattr(inst, 'lp_rate'):
                        inst.lp_rate = lp_rate
                    if hasattr(inst, 'lp_amount'):
                        inst.lp_amount = inst.balance * lp_rate * day_fraction
                    inst_matched = True

            # ── CLP ──────────────────────────────────────────────────────────
            clp_rule = components.get("CLP")
            if clp_rule:
                clp_rate = _moving_avg_rate(clp_rule, as_of_date)
                if clp_rate is not None:
                    if hasattr(inst, 'clp_rate'):
                        inst.clp_rate = clp_rate
                    if hasattr(inst, 'clp_amount'):
                        inst.clp_amount = inst.balance * clp_rate * day_fraction
                    inst_matched = True

            # ── BUF ──────────────────────────────────────────────────────────
            buf_rule = components.get("BUF")
            if buf_rule:
                buf_rate = _moving_avg_rate(buf_rule, as_of_date)
                if buf_rate is not None:
                    if hasattr(inst, 'buffer_rate'):
                        inst.buffer_rate = buf_rate
                    if hasattr(inst, 'buffer_amount'):
                        inst.buffer_amount = inst.balance * buf_rate * day_fraction
                    inst_matched = True

            if inst_matched:
                matched += 1
            else:
                skipped += 1

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
