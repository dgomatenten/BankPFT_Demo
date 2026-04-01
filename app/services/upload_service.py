"""Excel upload parsing and validation service."""

import uuid
import json
from datetime import datetime
import pandas as pd
from werkzeug.utils import secure_filename
from app.models import db
from app.models.dimensions import DimOrgUnit, DimProduct, DimCustomer, DimAccount
from app.models.staging import StgInstData, StgGlData
from app.models.allocation import RefStaticAllocation
from app.models.workflow import UploadBatch


ALLOWED_EXTENSIONS = {"xlsx", "csv"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _read_file(filepath: str) -> pd.DataFrame:
    if filepath.endswith(".csv"):
        return pd.read_csv(filepath)
    return pd.read_excel(filepath, engine="openpyxl")


def validate_instrument_data(df: pd.DataFrame) -> list[str]:
    """Validate instrument upload data against dimension tables."""
    errors = []

    # Technical checks
    required_cols = ["as_of_date", "account_id", "customer_id", "product_code", "org_unit_id", "balance"]
    for col in required_cols:
        if col not in df.columns:
            errors.append(f"Missing required column: {col}")
    if errors:
        return errors

    if df[required_cols].isnull().any().any():
        null_cols = df[required_cols].columns[df[required_cols].isnull().any()].tolist()
        errors.append(f"Null values found in: {null_cols}")

    if df["account_id"].duplicated().any():
        errors.append("Duplicate account_id values found.")

    # Dimension checks
    valid_customers = {c.customer_id for c in DimCustomer.query.all()}
    bad_customers = set(df["customer_id"].astype(str)) - valid_customers
    if bad_customers:
        errors.append(f"Unknown customer_ids: {sorted(bad_customers)[:10]}")

    valid_products = {p.product_code for p in DimProduct.query.all()}
    bad_products = set(df["product_code"].astype(str)) - valid_products
    if bad_products:
        errors.append(f"Unknown product_codes: {sorted(bad_products)[:10]}")

    valid_orgs = {o.org_unit_id for o in DimOrgUnit.query.all()}
    bad_orgs = set(df["org_unit_id"].astype(str)) - valid_orgs
    if bad_orgs:
        errors.append(f"Unknown org_unit_ids: {sorted(bad_orgs)[:10]}")

    return errors


def validate_gl_data(df: pd.DataFrame) -> list[str]:
    errors = []
    required_cols = ["as_of_date", "gl_account", "org_unit_id", "balance"]
    for col in required_cols:
        if col not in df.columns:
            errors.append(f"Missing required column: {col}")
    if errors:
        return errors

    if df[required_cols].isnull().any().any():
        null_cols = df[required_cols].columns[df[required_cols].isnull().any()].tolist()
        errors.append(f"Null values found in: {null_cols}")

    valid_orgs = {o.org_unit_id for o in DimOrgUnit.query.all()}
    bad_orgs = set(df["org_unit_id"].astype(str)) - valid_orgs
    if bad_orgs:
        errors.append(f"Unknown org_unit_ids: {sorted(bad_orgs)[:10]}")

    return errors


def validate_allocation_data(df: pd.DataFrame) -> list[str]:
    errors = []
    required_cols = ["allocation_id", "customer_id", "source_org_unit_id", "target_org_unit_id", "ratio"]
    for col in required_cols:
        if col not in df.columns:
            errors.append(f"Missing required column: {col}")
    if errors:
        return errors

    if df[required_cols].isnull().any().any():
        null_cols = df[required_cols].columns[df[required_cols].isnull().any()].tolist()
        errors.append(f"Null values found in: {null_cols}")

    # Ratio check: per allocation_id + customer_id, sum must be 1.0
    grouped = df.groupby(["allocation_id", "customer_id"])["ratio"].sum()
    bad_ratios = grouped[abs(grouped - 1.0) > 0.001]
    if not bad_ratios.empty:
        for (alloc_id, cust_id), total in bad_ratios.items():
            errors.append(
                f"Ratio sum for allocation_id={alloc_id}, customer_id={cust_id} "
                f"is {total:.4f}, expected 1.0"
            )

    # Dimension checks
    valid_customers = {c.customer_id for c in DimCustomer.query.all()}
    bad_customers = set(df["customer_id"].astype(str)) - valid_customers
    if bad_customers:
        errors.append(f"Unknown customer_ids: {sorted(bad_customers)[:10]}")

    valid_orgs = {o.org_unit_id for o in DimOrgUnit.query.all()}
    bad_src = set(df["source_org_unit_id"].astype(str)) - valid_orgs
    bad_tgt = set(df["target_org_unit_id"].astype(str)) - valid_orgs
    if bad_src:
        errors.append(f"Unknown source_org_unit_ids: {sorted(bad_src)[:10]}")
    if bad_tgt:
        errors.append(f"Unknown target_org_unit_ids: {sorted(bad_tgt)[:10]}")

    return errors


def process_upload(filepath: str, data_type: str, maker_id: str) -> UploadBatch:
    """Parse an uploaded file, validate, and store in staging."""
    batch_id = str(uuid.uuid4())
    df = _read_file(filepath)

    validators = {
        "INSTRUMENT": validate_instrument_data,
        "GL": validate_gl_data,
        "ALLOCATION": validate_allocation_data,
    }
    validator = validators.get(data_type)
    errors = validator(df) if validator else [f"Unknown data type: {data_type}"]

    batch = UploadBatch(
        id=batch_id,
        data_type=data_type,
        filename=secure_filename(filepath.split("/")[-1]),
        status="DRAFT" if errors else "PENDING",
        row_count=len(df),
        error_count=len(errors),
        errors_json=json.dumps(errors) if errors else None,
        maker_id=maker_id,
    )
    db.session.add(batch)

    # If no validation errors, load into staging
    if not errors:
        if data_type == "INSTRUMENT":
            for _, row in df.iterrows():
                db.session.add(StgInstData(
                    upload_batch_id=batch_id,
                    as_of_date=pd.to_datetime(row["as_of_date"]).date(),
                    account_id=str(row["account_id"]),
                    customer_id=str(row["customer_id"]),
                    product_code=str(row["product_code"]),
                    org_unit_id=str(row["org_unit_id"]),
                    balance=float(row["balance"]),
                    interest_income=float(row.get("interest_income", 0)),
                ))
        elif data_type == "GL":
            for _, row in df.iterrows():
                db.session.add(StgGlData(
                    upload_batch_id=batch_id,
                    as_of_date=pd.to_datetime(row["as_of_date"]).date(),
                    gl_account=str(row["gl_account"]),
                    org_unit_id=str(row["org_unit_id"]),
                    debit=float(row.get("debit", 0)),
                    credit=float(row.get("credit", 0)),
                    balance=float(row["balance"]),
                ))
        elif data_type == "ALLOCATION":
            for _, row in df.iterrows():
                db.session.add(RefStaticAllocation(
                    upload_batch_id=batch_id,
                    allocation_id=str(row["allocation_id"]),
                    customer_id=str(row["customer_id"]),
                    source_org_unit_id=str(row["source_org_unit_id"]),
                    target_org_unit_id=str(row["target_org_unit_id"]),
                    ratio=float(row["ratio"]),
                    status="PENDING",
                    maker_id=maker_id,
                ))

    db.session.commit()
    return batch
