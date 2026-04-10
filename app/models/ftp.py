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


class FtpModel(db.Model):
    """Groups FTP pricing parameter rules into distinct executable models."""
    __tablename__ = "ftp_model"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    model_name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    rules = db.relationship("FtpModelRule", backref="ftp_model", lazy="dynamic", cascade="all, delete-orphan")


class FtpModelRule(db.Model):
    """Pricing parameters for one FTP component (COF/LP/CLP) mapped to a product within an FTP Model."""
    __tablename__ = "ftp_model_rule"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ftp_model_id = db.Column(db.Integer, db.ForeignKey("ftp_model.id", ondelete="CASCADE"), nullable=False)
    product_code = db.Column(db.String(20), db.ForeignKey("dim_product.product_code"), nullable=False)
    component = db.Column(db.String(3), nullable=False, default="COF")  # COF | LP | CLP
    method = db.Column(db.String(20), default="MOVING_AVG")
    rate_code = db.Column(db.String(20), nullable=False)
    term = db.Column(db.Integer, nullable=False)
    term_mult = db.Column(db.String(1), nullable=False)
    avg_period = db.Column(db.Integer, nullable=False, default=1)
    avg_period_mult = db.Column(db.String(1), nullable=False, default="M")
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class FtpProcess(db.Model):
    """Executable batch hooks mapping FTP Models directly to database structures."""
    __tablename__ = "ftp_process"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    process_name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    ftp_model_id = db.Column(db.Integer, db.ForeignKey("ftp_model.id"), nullable=False)
    target_table = db.Column(db.String(100), nullable=False, default="stg_inst_data")
    filter_json = db.Column(db.JSON, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    ftp_model_rel = db.relationship("FtpModel", backref="processes")


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
