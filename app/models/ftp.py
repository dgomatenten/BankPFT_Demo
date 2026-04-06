from app.models import db
from app.core.time_utils import utc_now


class RefInterestRate(db.Model):
    """Interest rate curve data — uploaded and maker/checker approved."""
    __tablename__ = "ref_interest_rate"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    upload_batch_id = db.Column(db.String(36), nullable=True, index=True)
    effective_date = db.Column(db.Date, nullable=False)
    interest_rate_code = db.Column(db.String(20), nullable=False)
    # term + term_mult represent the tenor, e.g. term=1, term_mult='M' → 1M
    term = db.Column(db.Integer, nullable=False)
    term_mult = db.Column(db.String(1), nullable=False)   # D=day  M=month  Y=year
    rate = db.Column(db.Numeric(10, 6), nullable=False)             # decimal, e.g. 0.05 = 5 %
    status = db.Column(db.String(20), default="DRAFT")     # DRAFT PENDING APPROVED REJECTED
    maker_id = db.Column(db.String(50), nullable=False)
    checker_id = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class FtpProductConfig(db.Model):
    """FTP calculation configuration per product code."""
    __tablename__ = "ftp_product_config"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    product_code = db.Column(db.String(20), nullable=False, unique=True)
    method = db.Column(db.String(20), default="MOVING_AVG")  # MOVING_AVG (only supported now)
    rate_code = db.Column(db.String(20), nullable=False)      # interest_rate_code to look up
    # Tenor of the rate point to use, e.g. term=3, term_mult='M' → 3M rate
    term = db.Column(db.Integer, nullable=False)
    term_mult = db.Column(db.String(1), nullable=False)        # D, M, Y
    # Moving-average lookback window, e.g. avg_period=1, avg_period_mult='M' → 1-month MA
    avg_period = db.Column(db.Integer, nullable=False, default=1)
    avg_period_mult = db.Column(db.String(1), nullable=False, default="M")  # D, M, Y
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class FtpRun(db.Model):
    """Tracks each FTP calculation run."""
    __tablename__ = "ftp_run"

    id = db.Column(db.String(36), primary_key=True)
    as_of_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default="RUNNING")   # RUNNING COMPLETED FAILED
    run_by = db.Column(db.String(50), nullable=True)
    instruments_processed = db.Column(db.Integer, default=0)
    instruments_matched = db.Column(db.Integer, default=0)
    instruments_skipped = db.Column(db.Integer, default=0)
    started_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    error_message = db.Column(db.Text, nullable=True)
