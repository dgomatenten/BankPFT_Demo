from app.models import db
from app.core.time_utils import utc_now


class DimOrgUnit(db.Model):
    __tablename__ = "dim_org_unit"
    org_unit_id = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    parent_id = db.Column(db.String(20), db.ForeignKey("dim_org_unit.org_unit_id"), nullable=True)
    is_leaf = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utc_now)


class DimProduct(db.Model):
    __tablename__ = "dim_product"
    product_code = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50))
    is_leaf = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utc_now)


class DimCustomer(db.Model):
    __tablename__ = "dim_customer"
    customer_id = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    segment = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=utc_now)


class DimAccount(db.Model):
    __tablename__ = "dim_account"
    account_id = db.Column(db.String(20), primary_key=True)
    customer_id = db.Column(db.String(20), db.ForeignKey("dim_customer.customer_id"), nullable=False)
    product_code = db.Column(db.String(20), db.ForeignKey("dim_product.product_code"), nullable=False)
    org_unit_id = db.Column(db.String(20), db.ForeignKey("dim_org_unit.org_unit_id"), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now)
