from app.models import db
from app.core.time_utils import utc_now
from app.models.mixins import TimestampMixin, MakerCheckerMixin
import uuid


class UploadBatch(MakerCheckerMixin, db.Model):
    """Tracks every file upload and its lifecycle through Maker/Checker."""
    __tablename__ = "upload_batch"
    id = db.Column(db.String(36), primary_key=True)
    data_type = db.Column(db.String(20), nullable=False)  # INSTRUMENT, GL, ALLOCATION
    filename = db.Column(db.String(255), nullable=False)
    row_count = db.Column(db.Integer, default=0)
    error_count = db.Column(db.Integer, default=0)
    errors_json = db.Column(db.Text, nullable=True)
    maker_comment = db.Column(db.Text, nullable=True)
    checker_comment = db.Column(db.Text, nullable=True)


class AllocationRule(TimestampMixin, db.Model):
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
    output_dim_json = db.Column(db.Text, nullable=True)  # per-dimension output mapping for DEBIT
    credit_dim_json = db.Column(db.Text, nullable=True)  # per-dimension output mapping for CREDIT
    allocation_method = db.Column(db.String(20), default="RATIO")  # RATIO | DISTRIBUTION | STATIC
    distribution_driver = db.Column(db.String(100), nullable=True)  # driver_name for DISTRIBUTION method
    entry_mode = db.Column(db.String(20), default="BOTH")   # BOTH | DEBIT_ONLY | CREDIT_ONLY
    generate_offset = db.Column(db.Boolean, default=True)   # legacy
    offset_account = db.Column(db.String(50), nullable=True)  # legacy
    is_active = db.Column(db.Boolean, default=True)
    status = db.Column(db.String(20), default="ACTIVE")
    created_by = db.Column(db.String(50), nullable=True)


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
    started_at = db.Column(db.DateTime, default=utc_now)
    completed_at = db.Column(db.DateTime, nullable=True)
    run_by = db.Column(db.String(50), nullable=False)
    error_message = db.Column(db.Text, nullable=True)


# ─────────────────────────────────────────────────────────────────────────────
# Multi-task Batch Definition & Execution
# ─────────────────────────────────────────────────────────────────────────────

class BatchDefinition(TimestampMixin, db.Model):
    """A named, ordered sequence of batch tasks (allocation, FTP, data file, custom SP)."""
    __tablename__ = "batch_definition"
    id                = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name              = db.Column(db.String(100), nullable=False, unique=True)
    description       = db.Column(db.Text, nullable=True)
    continue_on_error = db.Column(db.Boolean, default=False)
    is_active         = db.Column(db.Boolean, default=True)
    created_by        = db.Column(db.String(50), nullable=True)
    tasks             = db.relationship(
        "BatchTask", backref="definition",
        order_by="BatchTask.step_order", cascade="all, delete-orphan", lazy="select"
    )
    executions        = db.relationship(
        "BatchExecution", backref="definition",
        order_by="BatchExecution.started_at.desc()", lazy="dynamic"
    )


TASK_TYPES = ("ALLOCATION", "FTP", "DATAFILE_IMPORT", "DATAFILE_EXPORT", "CUSTOM_SP")


class BatchTask(db.Model):
    """One ordered step inside a BatchDefinition."""
    __tablename__ = "batch_task"
    id            = db.Column(db.Integer, primary_key=True, autoincrement=True)
    definition_id = db.Column(db.Integer, db.ForeignKey("batch_definition.id"), nullable=False)
    step_order    = db.Column(db.Integer, nullable=False, default=0)
    task_type     = db.Column(db.String(30), nullable=False)   # one of TASK_TYPES
    ref_id        = db.Column(db.String(100), nullable=True)   # rule_id | format_id | export_id | sp_name
    label         = db.Column(db.String(200), nullable=True)   # human-readable


class BatchExecution(db.Model):
    """Top-level run record for a single execution of a BatchDefinition."""
    __tablename__ = "batch_execution"
    id            = db.Column(db.String(36), primary_key=True,
                              default=lambda: str(uuid.uuid4()))
    definition_id = db.Column(db.Integer, db.ForeignKey("batch_definition.id"), nullable=False)
    as_of_date    = db.Column(db.Date, nullable=False)
    status        = db.Column(db.String(20), default="RUNNING")  # RUNNING|COMPLETED|FAILED|PARTIAL
    started_at    = db.Column(db.DateTime, default=utc_now)
    completed_at  = db.Column(db.DateTime, nullable=True)
    run_by        = db.Column(db.String(50), nullable=False)
    error_message = db.Column(db.Text, nullable=True)
    steps         = db.relationship(
        "BatchExecutionStep", backref="execution",
        order_by="BatchExecutionStep.step_order", cascade="all, delete-orphan", lazy="select"
    )


class BatchExecutionStep(db.Model):
    """Per-task result row within a BatchExecution."""
    __tablename__ = "batch_execution_step"
    id            = db.Column(db.Integer, primary_key=True, autoincrement=True)
    execution_id  = db.Column(db.String(36), db.ForeignKey("batch_execution.id"), nullable=False)
    step_order    = db.Column(db.Integer, nullable=False)
    task_type     = db.Column(db.String(30), nullable=False)
    ref_id        = db.Column(db.String(100), nullable=True)
    label         = db.Column(db.String(200), nullable=True)
    status        = db.Column(db.String(20), default="PENDING")  # PENDING|RUNNING|COMPLETED|FAILED|SKIPPED
    ref_run_id    = db.Column(db.String(36), nullable=True)      # ID of created underlying run record
    started_at    = db.Column(db.DateTime, nullable=True)
    completed_at  = db.Column(db.DateTime, nullable=True)
    summary       = db.Column(db.Text, nullable=True)
    error_message = db.Column(db.Text, nullable=True)


class PostApprovalLog(db.Model):
    """Records each post-approval action triggered when an UploadBatch is approved.

    action_type: "run_rules"        — ran one or more AllocationRules
                 "stored_procedure" — placeholder SP call (POC)
    status:      "SUCCESS" | "FAILED" | "SKIPPED"
    """
    __tablename__ = "post_approval_log"
    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    upload_batch_id = db.Column(db.String(36), db.ForeignKey("upload_batch.id"),
                                nullable=False, index=True)
    action_type     = db.Column(db.String(20), nullable=False)   # run_rules | stored_procedure
    action_ref      = db.Column(db.String(200), nullable=True)   # rule ID(s) CSV or procedure name
    status          = db.Column(db.String(20), nullable=False)   # SUCCESS | FAILED | SKIPPED
    detail          = db.Column(db.Text, nullable=True)          # summary or error message
    executed_at     = db.Column(db.DateTime, default=utc_now)
    executed_by     = db.Column(db.String(50), nullable=False)
