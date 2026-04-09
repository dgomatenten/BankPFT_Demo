from app.models import db
from app.core.time_utils import utc_now


class StgInstData(db.Model):
    __tablename__ = "stg_inst_data"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    upload_batch_id = db.Column(db.String(36), nullable=False)
    as_of_date = db.Column(db.Date, nullable=False)
    transaction_number = db.Column(db.String(100), nullable=True)
    account_id = db.Column(db.String(20), nullable=False)
    customer_id = db.Column(db.String(20), nullable=False)
    product_code = db.Column(db.String(20), nullable=False)
    org_unit_id = db.Column(db.String(20), nullable=False)
    balance = db.Column(db.Numeric(18, 6), nullable=False)
    interest_income = db.Column(db.Numeric(18, 6), default=0.0)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)


class ProcInstData(db.Model):
    __tablename__ = "proc_inst_data"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    upload_batch_id = db.Column(db.String(36), nullable=False)
    as_of_date = db.Column(db.Date, nullable=False)
    transaction_number = db.Column(db.String(100), nullable=True)
    account_id = db.Column(db.String(20), nullable=False)
    customer_id = db.Column(db.String(20), nullable=False)
    product_code = db.Column(db.String(20), nullable=False)
    org_unit_id = db.Column(db.String(20), nullable=False)
    balance = db.Column(db.Numeric(18, 6), nullable=False)
    interest_income = db.Column(db.Numeric(18, 6), default=0.0)
    base_rate = db.Column(db.Numeric(18, 6), nullable=True)         # filled by FTP engine
    cost_of_fund = db.Column(db.Numeric(18, 6), nullable=True)      # filled by FTP engine
    validated_at = db.Column(db.DateTime(timezone=True), default=utc_now)


class StgGlData(db.Model):
    __tablename__ = "stg_gl_data"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    upload_batch_id = db.Column(db.String(36), nullable=False)
    as_of_date = db.Column(db.Date, nullable=False)
    gl_account = db.Column(db.String(20), nullable=False)
    org_unit_id = db.Column(db.String(20), nullable=False)
    debit = db.Column(db.Numeric(18, 6), default=0.0)
    credit = db.Column(db.Numeric(18, 6), default=0.0)
    balance = db.Column(db.Numeric(18, 6), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)


class ProcGlData(db.Model):
    __tablename__ = "proc_gl_data"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    upload_batch_id = db.Column(db.String(36), nullable=False)
    as_of_date = db.Column(db.Date, nullable=False)
    gl_account = db.Column(db.String(20), nullable=False)
    org_unit_id = db.Column(db.String(20), nullable=False)
    debit = db.Column(db.Numeric(18, 6), default=0.0)
    credit = db.Column(db.Numeric(18, 6), default=0.0)
    balance = db.Column(db.Numeric(18, 6), nullable=False)
    validated_at = db.Column(db.DateTime(timezone=True), default=utc_now)
