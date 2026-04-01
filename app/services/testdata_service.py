"""Test data generation service."""

import uuid
import random
from datetime import date
import pandas as pd
import os
from app.models import db
from app.models.dimensions import DimOrgUnit, DimProduct, DimCustomer, DimAccount
from app.models.staging import ProcInstData
from app.models.allocation import RefStaticAllocation


def generate_master_data():
    """Generate 10 Org Units, 5 Products, 50 Customers, and Accounts."""
    # Org Units
    orgs = []
    org_parent = DimOrgUnit(org_unit_id="ORG-HQ", name="Head Office", is_leaf=False)
    orgs.append(org_parent)
    for i in range(1, 11):
        orgs.append(DimOrgUnit(
            org_unit_id=f"ORG-{i:03d}",
            name=f"Branch {i}",
            parent_id="ORG-HQ",
            is_leaf=True,
        ))
    for o in orgs:
        if not DimOrgUnit.query.get(o.org_unit_id):
            db.session.add(o)

    # Products
    product_names = [
        ("PROD-LON", "Personal Loan"),
        ("PROD-MTG", "Mortgage"),
        ("PROD-DEP", "Term Deposit"),
        ("PROD-SAV", "Savings Account"),
        ("PROD-CRD", "Credit Card"),
    ]
    for code, name in product_names:
        if not DimProduct.query.get(code):
            db.session.add(DimProduct(product_code=code, name=name, category="Retail", is_leaf=True))

    # Customers
    for i in range(1, 51):
        cid = f"CUST-{i:04d}"
        if not DimCustomer.query.get(cid):
            segments = ["Retail", "Corporate", "SME", "Private Banking"]
            db.session.add(DimCustomer(
                customer_id=cid,
                name=f"Customer {i}",
                segment=random.choice(segments),
            ))

    db.session.commit()

    # Accounts  (one per customer-product combo for first 10 customers)
    products = [p[0] for p in product_names]
    org_ids = [f"ORG-{i:03d}" for i in range(1, 11)]
    for i in range(1, 11):
        for prod in products:
            aid = f"ACC-{i:04d}-{prod}"
            if not DimAccount.query.get(aid):
                db.session.add(DimAccount(
                    account_id=aid,
                    customer_id=f"CUST-{i:04d}",
                    product_code=prod,
                    org_unit_id=random.choice(org_ids),
                ))

    db.session.commit()
    return {"org_units": 11, "products": 5, "customers": 50, "accounts": 50}


def generate_instrument_data(as_of_date=None):
    """Generate 500+ instrument records in proc_inst_data."""
    if as_of_date is None:
        as_of_date = date.today()

    accounts = DimAccount.query.all()
    if not accounts:
        return 0

    batch_id = str(uuid.uuid4())
    count = 0
    for acc in accounts:
        for _ in range(random.randint(8, 12)):
            db.session.add(ProcInstData(
                upload_batch_id=batch_id,
                as_of_date=as_of_date,
                account_id=acc.account_id,
                customer_id=acc.customer_id,
                product_code=acc.product_code,
                org_unit_id=acc.org_unit_id,
                balance=round(random.uniform(1000, 500000), 2),
                interest_income=round(random.uniform(10, 5000), 2),
            ))
            count += 1

    db.session.commit()
    return count


def generate_allocation_ratios():
    """Generate sample allocation ratios for first 10 customers."""
    org_ids = [f"ORG-{i:03d}" for i in range(1, 11)]
    count = 0
    for i in range(1, 11):
        cust_id = f"CUST-{i:04d}"
        alloc_id = str(uuid.uuid4())
        source_org = random.choice(org_ids)

        # Split across 2-4 target orgs
        n_targets = random.randint(2, 4)
        targets = random.sample(org_ids, n_targets)
        ratios = [random.random() for _ in range(n_targets)]
        total = sum(ratios)
        ratios = [round(r / total, 4) for r in ratios]
        # Fix rounding
        ratios[-1] = round(1.0 - sum(ratios[:-1]), 4)

        for org, ratio in zip(targets, ratios):
            db.session.add(RefStaticAllocation(
                allocation_id=alloc_id,
                customer_id=cust_id,
                source_org_unit_id=source_org,
                target_org_unit_id=org,
                ratio=ratio,
                status="APPROVED",
                maker_id="system",
                checker_id="system",
            ))
            count += 1

    db.session.commit()
    return count


def generate_allocation_template_with_data(output_dir: str) -> tuple[str, int]:
    """Generate an Excel template for allocation ratios pre-filled with sample data.

    Uses existing customers and org units from master data. Each customer is
    split across 2-4 random target org units with ratios summing to 1.0.
    """
    customers = DimCustomer.query.all()
    org_units = DimOrgUnit.query.filter_by(is_leaf=True).all()

    if not customers or not org_units:
        raise ValueError("Generate master data first (need customers and org units).")

    org_ids = [o.org_unit_id for o in org_units]
    rows = []

    for cust in customers:
        alloc_id = str(uuid.uuid4())
        source_org = random.choice(org_ids)
        n_targets = random.randint(2, 4)
        targets = random.sample(org_ids, min(n_targets, len(org_ids)))

        # Build ratios that sum to exactly 1.0
        raw = [random.random() for _ in range(len(targets))]
        total = sum(raw)
        ratios = [round(r / total, 4) for r in raw]
        ratios[-1] = round(1.0 - sum(ratios[:-1]), 4)

        for tgt, ratio in zip(targets, ratios):
            rows.append({
                "allocation_id": alloc_id,
                "customer_id": cust.customer_id,
                "source_org_unit_id": source_org,
                "target_org_unit_id": tgt,
                "ratio": ratio,
            })

    df = pd.DataFrame(rows)
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "allocation_ratio_testdata.xlsx")
    df.to_excel(path, index=False, engine="openpyxl")
    return path, len(rows)


def generate_excel_templates(output_dir: str) -> list[str]:
    """Generate empty Excel templates with correct headers."""
    templates = {
        "instrument_template.xlsx": [
            "as_of_date", "account_id", "customer_id", "product_code",
            "org_unit_id", "balance", "interest_income"
        ],
        "gl_template.xlsx": [
            "as_of_date", "gl_account", "org_unit_id", "debit", "credit", "balance"
        ],
        "allocation_template.xlsx": [
            "allocation_id", "customer_id", "source_org_unit_id",
            "target_org_unit_id", "ratio"
        ],
    }

    os.makedirs(output_dir, exist_ok=True)
    files = []
    for fname, cols in templates.items():
        path = os.path.join(output_dir, fname)
        df = pd.DataFrame(columns=cols)
        df.to_excel(path, index=False, engine="openpyxl")
        files.append(path)

    return files
