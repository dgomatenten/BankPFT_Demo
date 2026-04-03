from app.models import db
from datetime import datetime


class StgInstData(db.Model):
    __tablename__ = "stg_inst_data"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    upload_batch_id = db.Column(db.String(36), nullable=False)
    as_of_date = db.Column(db.Date, nullable=False)
    account_id = db.Column(db.String(20), nullable=False)
    customer_id = db.Column(db.String(20), nullable=False)
    product_code = db.Column(db.String(20), nullable=False)
    org_unit_id = db.Column(db.String(20), nullable=False)
    balance = db.Column(db.Float, nullable=False)
    interest_income = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ProcInstData(db.Model):
    __tablename__ = "proc_inst_data"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    upload_batch_id = db.Column(db.String(36), nullable=False)
    as_of_date = db.Column(db.Date, nullable=False)
    account_id = db.Column(db.String(20), nullable=False)
    customer_id = db.Column(db.String(20), nullable=False)
    product_code = db.Column(db.String(20), nullable=False)
    org_unit_id = db.Column(db.String(20), nullable=False)
    balance = db.Column(db.Float, nullable=False)
    interest_income = db.Column(db.Float, default=0.0)
    base_rate = db.Column(db.Float, nullable=True)         # filled by FTP engine
    cost_of_fund = db.Column(db.Float, nullable=True)      # filled by FTP engine
    validated_at = db.Column(db.DateTime, default=datetime.utcnow)


class StgGlData(db.Model):
    __tablename__ = "stg_gl_data"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    upload_batch_id = db.Column(db.String(36), nullable=False)
    as_of_date = db.Column(db.Date, nullable=False)
    gl_account = db.Column(db.String(20), nullable=False)
    org_unit_id = db.Column(db.String(20), nullable=False)
    debit = db.Column(db.Float, default=0.0)
    credit = db.Column(db.Float, default=0.0)
    balance = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ProcGlData(db.Model):
    __tablename__ = "proc_gl_data"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    upload_batch_id = db.Column(db.String(36), nullable=False)
    as_of_date = db.Column(db.Date, nullable=False)
    gl_account = db.Column(db.String(20), nullable=False)
    org_unit_id = db.Column(db.String(20), nullable=False)
    debit = db.Column(db.Float, default=0.0)
    credit = db.Column(db.Float, default=0.0)
    balance = db.Column(db.Float, nullable=False)
    validated_at = db.Column(db.DateTime, default=datetime.utcnow)
