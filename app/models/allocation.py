from app.models import db
from datetime import datetime


class RefStaticAllocation(db.Model):
    __tablename__ = "ref_static_allocation"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    upload_batch_id = db.Column(db.String(36), nullable=True, index=True)
    allocation_id = db.Column(db.String(36), nullable=False, index=True)
    customer_id = db.Column(db.String(20), db.ForeignKey("dim_customer.customer_id"), nullable=False)
    source_org_unit_id = db.Column(db.String(20), db.ForeignKey("dim_org_unit.org_unit_id"), nullable=False)
    target_org_unit_id = db.Column(db.String(20), db.ForeignKey("dim_org_unit.org_unit_id"), nullable=False)
    ratio = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default="DRAFT")  # DRAFT, PENDING, APPROVED, REJECTED
    maker_id = db.Column(db.String(50), nullable=False)
    checker_id = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    comments = db.Column(db.Text, nullable=True)


class RefOrgReclass(db.Model):
    __tablename__ = "ref_org_reclass"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    upload_batch_id = db.Column(db.String(36), nullable=True, index=True)
    reclass_id = db.Column(db.String(36), nullable=False, index=True)
    source_org_unit_id = db.Column(db.String(20), db.ForeignKey("dim_org_unit.org_unit_id"), nullable=False)
    target_org_unit_id = db.Column(db.String(20), db.ForeignKey("dim_org_unit.org_unit_id"), nullable=False)
    ratio = db.Column(db.Float, nullable=False, default=1.0)
    status = db.Column(db.String(20), default="DRAFT")
    maker_id = db.Column(db.String(50), nullable=False)
    checker_id = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    comments = db.Column(db.Text, nullable=True)


class FctMgmtLedger(db.Model):
    __tablename__ = "fct_mgmt_ledger"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    batch_run_id = db.Column(db.String(36), nullable=False, index=True)
    as_of_date = db.Column(db.Date, nullable=False)
    allocation_id = db.Column(db.String(36), nullable=True)
    source_account_id = db.Column(db.String(20), nullable=False)
    customer_id = db.Column(db.String(20), nullable=False)
    product_code = db.Column(db.String(20), nullable=False)
    source_org_unit_id = db.Column(db.String(20), nullable=False)
    target_org_unit_id = db.Column(db.String(20), nullable=False)
    source_balance = db.Column(db.Float, nullable=False)
    allocated_balance = db.Column(db.Float, nullable=False)
    allocated_income = db.Column(db.Float, default=0.0)
    ratio_applied = db.Column(db.Float, nullable=False)
    is_orphan = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
