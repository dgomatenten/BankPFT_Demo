from app.models import db
from app.core.time_utils import utc_now
from app.models.mixins import MakerCheckerMixin


class RefStaticAllocation(MakerCheckerMixin, db.Model):
    __tablename__ = "ref_static_allocation"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    upload_batch_id = db.Column(db.String(36), nullable=True, index=True)
    allocation_id = db.Column(db.String(36), nullable=False, index=True)
    customer_id = db.Column(db.String(20), db.ForeignKey("dim_customer.customer_id"), nullable=False)
    source_org_unit_id = db.Column(db.String(20), db.ForeignKey("dim_org_unit.org_unit_id"), nullable=False)
    target_org_unit_id = db.Column(db.String(20), db.ForeignKey("dim_org_unit.org_unit_id"), nullable=False)
    ratio = db.Column(db.Numeric(10, 6), nullable=False)
    comments = db.Column(db.Text, nullable=True)


class RefOrgReclass(MakerCheckerMixin, db.Model):
    __tablename__ = "ref_org_reclass"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    upload_batch_id = db.Column(db.String(36), nullable=True, index=True)
    reclass_id = db.Column(db.String(36), nullable=False, index=True)
    source_org_unit_id = db.Column(db.String(20), db.ForeignKey("dim_org_unit.org_unit_id"), nullable=False)
    target_org_unit_id = db.Column(db.String(20), db.ForeignKey("dim_org_unit.org_unit_id"), nullable=False)
    ratio = db.Column(db.Numeric(10, 6), nullable=False, default=1.0)
    comments = db.Column(db.Text, nullable=True)


class RefStaticDistribution(MakerCheckerMixin, db.Model):
    """Distribution table for Static Distribution allocation method.

    Each row maps a source dimension value to a target dimension (target_dim)
    with a ratio.  Use distribution_id to group rows that belong to the same
    distribution set (ratios per distribution_id should sum to 1.0).
    """
    __tablename__ = "ref_static_distribution"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    upload_batch_id = db.Column(db.String(36), nullable=True, index=True)
    driver_name = db.Column(db.String(100), nullable=False, index=True, default="")
    distribution_id = db.Column(db.String(50), nullable=False, index=True)
    # Source join columns — populate the one that matches the rule's join_key
    customer_id = db.Column(db.String(20), nullable=True, index=True)
    org_unit_id = db.Column(db.String(20), nullable=True, index=True)
    product_code = db.Column(db.String(20), nullable=True, index=True)
    # Target
    target_dim = db.Column(db.String(50), nullable=False)
    ratio = db.Column(db.Numeric(10, 6), nullable=False)
    comments = db.Column(db.Text, nullable=True)


class RefStaticAlloc(MakerCheckerMixin, db.Model):
    """Simple source-to-target mapping for Static Allocation method.

    Used for 1:1 reclassification or aggregation.  The ratio defaults to 1.0;
    no splitting occurs.  The join_key column and target_dim are matched by
    the allocation engine at run time.
    """
    __tablename__ = "ref_static_alloc"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    upload_batch_id = db.Column(db.String(36), nullable=True, index=True)
    alloc_id = db.Column(db.String(50), nullable=False, index=True)
    # Source join columns — populate the one that matches the rule's join_key
    customer_id = db.Column(db.String(20), nullable=True, index=True)
    org_unit_id = db.Column(db.String(20), nullable=True, index=True)
    product_code = db.Column(db.String(20), nullable=True, index=True)
    # Target
    target_dim = db.Column(db.String(50), nullable=False)
    ratio = db.Column(db.Numeric(10, 6), nullable=False, default=1.0)
    comments = db.Column(db.Text, nullable=True)


class FctMgmtLedger(db.Model):
    """GL-level allocation output — one row per account per financial element per debit/credit entry."""
    __tablename__ = "fct_mgmt_ledger"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    batch_run_id = db.Column(db.String(36), nullable=False, index=True)
    as_of_date = db.Column(db.Date, nullable=False)
    entry_type = db.Column(db.String(10), default="DEBIT")  # DEBIT / CREDIT
    financial_element = db.Column(db.String(20), nullable=True)  # e.g. BAL, NII
    allocation_id = db.Column(db.String(36), nullable=True)
    source_account_id = db.Column(db.String(20), nullable=False)
    customer_id = db.Column(db.String(20), nullable=False)
    product_code = db.Column(db.String(20), nullable=False)
    source_org_unit_id = db.Column(db.String(20), nullable=False)
    target_org_unit_id = db.Column(db.String(20), nullable=False)
    source_balance = db.Column(db.Numeric(18, 6), nullable=False)
    allocated_balance = db.Column(db.Numeric(18, 6), nullable=False)
    allocated_income = db.Column(db.Numeric(18, 6), default=0.0)
    ratio_applied = db.Column(db.Numeric(10, 6), nullable=False)
    is_orphan = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)


class FctMgmtInstrument(db.Model):
    """Instrument-level allocation output — one row per account per financial element per debit/credit entry."""
    __tablename__ = "fct_mgmt_instrument"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    batch_run_id = db.Column(db.String(36), nullable=False, index=True)
    as_of_date = db.Column(db.Date, nullable=False)
    entry_type = db.Column(db.String(10), default="DEBIT")  # DEBIT / CREDIT
    financial_element = db.Column(db.String(20), nullable=True)  # e.g. BAL, NII
    allocation_id = db.Column(db.String(36), nullable=True)
    source_account_id = db.Column(db.String(20), nullable=False)
    customer_id = db.Column(db.String(20), nullable=False)
    product_code = db.Column(db.String(20), nullable=False)
    source_org_unit_id = db.Column(db.String(20), nullable=False)
    target_org_unit_id = db.Column(db.String(20), nullable=False)
    source_balance = db.Column(db.Numeric(18, 6), nullable=False)
    allocated_balance = db.Column(db.Numeric(18, 6), nullable=False)
    allocated_income = db.Column(db.Numeric(18, 6), default=0.0)
    ratio_applied = db.Column(db.Numeric(10, 6), nullable=False)
    is_orphan = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
