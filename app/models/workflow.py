from app.models import db
from datetime import datetime


class UploadBatch(db.Model):
    """Tracks every file upload and its lifecycle through Maker/Checker."""
    __tablename__ = "upload_batch"
    id = db.Column(db.String(36), primary_key=True)
    data_type = db.Column(db.String(20), nullable=False)  # INSTRUMENT, GL, ALLOCATION
    filename = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default="DRAFT")  # DRAFT, PENDING, APPROVED, REJECTED, PROCESSED
    row_count = db.Column(db.Integer, default=0)
    error_count = db.Column(db.Integer, default=0)
    errors_json = db.Column(db.Text, nullable=True)
    maker_id = db.Column(db.String(50), nullable=False)
    checker_id = db.Column(db.String(50), nullable=True)
    maker_comment = db.Column(db.Text, nullable=True)
    checker_comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AllocationRule(db.Model):
    """Configurable rule linking source -> lookup -> output."""
    __tablename__ = "allocation_rule"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    source_table = db.Column(db.String(50), default="proc_inst_data")
    lookup_table = db.Column(db.String(50), default="ref_static_allocation")
    output_table = db.Column(db.String(50), default="fct_mgmt_ledger")
    join_key = db.Column(db.String(50), default="customer_id")
    filter_json = db.Column(db.Text, nullable=True)  # JSON: {"logic":"AND","conditions":[...]}
    source_dim_json = db.Column(db.Text, nullable=True)  # per-dimension source member filter
    output_dim_json = db.Column(db.Text, nullable=True)  # per-dimension output mapping
    generate_offset = db.Column(db.Boolean, default=True)  # emit credit offset entry
    offset_account = db.Column(db.String(50), nullable=True)  # optional label for offset
    is_active = db.Column(db.Boolean, default=True)
    status = db.Column(db.String(20), default="ACTIVE")
    created_by = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BatchRun(db.Model):
    """Tracks each batch execution of allocation rules."""
    __tablename__ = "batch_run"
    id = db.Column(db.String(36), primary_key=True)
    rule_id = db.Column(db.Integer, db.ForeignKey("allocation_rule.id"), nullable=False)
    as_of_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default="RUNNING")  # RUNNING, COMPLETED, FAILED
    source_row_count = db.Column(db.Integer, default=0)
    output_row_count = db.Column(db.Integer, default=0)
    orphan_count = db.Column(db.Integer, default=0)
    source_total = db.Column(db.Float, default=0.0)
    output_total = db.Column(db.Float, default=0.0)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    run_by = db.Column(db.String(50), nullable=False)
    error_message = db.Column(db.Text, nullable=True)
