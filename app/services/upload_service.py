"""Excel upload parsing and validation service — driven by upload_config.json."""

import os
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

# ── Load configuration ──
_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "upload_config.json")
with open(_CONFIG_PATH) as _f:
    UPLOAD_CONFIG = json.load(_f)

ALLOWED_EXTENSIONS = set(UPLOAD_CONFIG["allowed_extensions"])

# Dimension model registry — maps config names to SQLAlchemy models + key columns
_DIMENSION_MODELS = {
    "dim_customer": (DimCustomer, "customer_id"),
    "dim_product": (DimProduct, "product_code"),
    "dim_org_unit": (DimOrgUnit, "org_unit_id"),
}

# Staging model registry — maps config names to SQLAlchemy models
_STAGING_MODELS = {
    "stg_inst_data": StgInstData,
    "stg_gl_data": StgGlData,
    "ref_static_allocation": RefStaticAllocation,
}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _read_file(filepath: str) -> pd.DataFrame:
    if filepath.endswith(".csv"):
        return pd.read_csv(filepath)
    return pd.read_excel(filepath, engine="openpyxl")


def _get_dimension_values(dim_name: str) -> set[str]:
    """Load valid values for a dimension from the database."""
    model, key_col = _DIMENSION_MODELS[dim_name]
    return {getattr(r, key_col) for r in model.query.all()}


def validate_upload(df: pd.DataFrame, data_type: str) -> list[str]:
    """Generic config-driven validator for any data type."""
    type_cfg = UPLOAD_CONFIG["data_types"].get(data_type)
    if not type_cfg:
        return [f"Unknown data type: {data_type}"]

    errors = []
    max_shown = UPLOAD_CONFIG.get("max_validation_errors_shown", 10)

    # 1. Required column check
    required_cols = type_cfg["required_columns"]
    for col in required_cols:
        if col not in df.columns:
            errors.append(f"Missing required column: {col}")
    if errors:
        return errors

    # 2. Null check on required columns
    if df[required_cols].isnull().any().any():
        null_cols = df[required_cols].columns[df[required_cols].isnull().any()].tolist()
        errors.append(f"Null values found in: {null_cols}")

    # 3. Unique key check
    unique_key = type_cfg.get("unique_key")
    if unique_key and unique_key in df.columns and df[unique_key].duplicated().any():
        errors.append(f"Duplicate {unique_key} values found.")

    # 4. Dimension lookups
    for col, dim_name in type_cfg.get("dimension_lookups", {}).items():
        if col not in df.columns:
            continue
        valid_values = _get_dimension_values(dim_name)
        bad_values = set(df[col].astype(str)) - valid_values
        if bad_values:
            errors.append(f"Unknown {col}: {sorted(bad_values)[:max_shown]}")

    # 5. Ratio validation (allocation-specific)
    ratio_cfg = type_cfg.get("ratio_validation")
    if ratio_cfg and ratio_cfg.get("enabled"):
        group_by = ratio_cfg["group_by"]
        sum_col = ratio_cfg["sum_column"]
        expected = ratio_cfg["expected_sum"]
        tolerance = ratio_cfg["tolerance"]
        if sum_col in df.columns and all(g in df.columns for g in group_by):
            grouped = df.groupby(group_by)[sum_col].sum()
            bad_ratios = grouped[abs(grouped - expected) > tolerance]
            if not bad_ratios.empty:
                for keys, total in bad_ratios.items():
                    label = ", ".join(f"{g}={k}" for g, k in zip(group_by, keys if isinstance(keys, tuple) else (keys,)))
                    errors.append(f"Ratio sum for {label} is {total:.4f}, expected {expected}")

    return errors


def _cast_value(value, col_cfg):
    """Cast a DataFrame cell value according to column_mapping config."""
    col_type = col_cfg["type"]
    if col_type == "date":
        return pd.to_datetime(value).date()
    elif col_type == "float":
        return float(value) if pd.notna(value) else col_cfg.get("default", 0)
    else:  # string
        return str(value)


def process_upload(filepath: str, data_type: str, maker_id: str) -> UploadBatch:
    """Parse an uploaded file, validate, and store in staging — config-driven."""
    batch_id = str(uuid.uuid4())
    df = _read_file(filepath)

    errors = validate_upload(df, data_type)

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

    # If no validation errors, load into staging using config
    if not errors:
        type_cfg = UPLOAD_CONFIG["data_types"][data_type]
        col_mapping = type_cfg["column_mapping"]
        staging_model = _STAGING_MODELS[type_cfg["staging_table"]]

        for _, row in df.iterrows():
            record_data = {"upload_batch_id": batch_id}
            for col_name, col_cfg in col_mapping.items():
                value = row.get(col_name, col_cfg.get("default"))
                record_data[col_name] = _cast_value(value, col_cfg)

            # Add extra fields for allocation records
            if data_type == "ALLOCATION":
                record_data["status"] = "PENDING"
                record_data["maker_id"] = maker_id

            db.session.add(staging_model(**record_data))

    db.session.commit()
    return batch
