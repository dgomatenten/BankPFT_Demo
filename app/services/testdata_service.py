"""Test data generation service."""

import uuid
import random
from datetime import date, timedelta
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
                transaction_number=f"TXN-{uuid.uuid4().hex[:8].upper()}",
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
                "as_of_date": date.today().isoformat()
            })

    df = pd.DataFrame(rows)
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "allocation_ratio_testdata.xlsx")
    df.to_excel(path, index=False, engine="openpyxl")
    return path, len(rows)


def generate_excel_templates(output_dir: str) -> list[str]:
    """Generate Excel templates pre-filled with sample data rows."""
    from datetime import date
    import random
    import uuid
    import pandas as pd
    import os

    today_str = date.today().isoformat()

    templates = {
        "instrument_template.xlsx": pd.DataFrame([{
            "as_of_date": today_str,
            "account_id": f"ACC-100{i}",
            "customer_id": f"CUST-{i:03d}",
            "product_code": "PROD-LON",
            "org_unit_id": "ORG-001",
            "transaction_number": f"TXN-{uuid.uuid4().hex[:8].upper()}",
            "balance": round(random.uniform(10000, 50000), 2),
            "interest_income": round(random.uniform(100, 500), 2)
        } for i in range(1, 4)]),

        "gl_template.xlsx": pd.DataFrame([{
            "as_of_date": today_str,
            "gl_account": f"GL-10{i}",
            "org_unit_id": "ORG-001",
            "debit": 5000.0 if i % 2 == 1 else 0.0,
            "credit": 0.0 if i % 2 == 1 else 5000.0,
            "balance": 5000.0 if i % 2 == 1 else -5000.0
        } for i in range(1, 4)]),

        "allocation_template.xlsx": pd.DataFrame([{
            "allocation_id": str(uuid.uuid4()),
            "customer_id": "CUST-001",
            "source_org_unit_id": "ORG-001",
            "target_org_unit_id": f"ORG-00{i+1}",
            "ratio": 0.5,
            "as_of_date": today_str
        } for i in range(1, 3)]),

        "interest_rate_template.xlsx": pd.DataFrame([{
            "effective_date": today_str,
            "interest_rate_code": "SWAP_RATE",
            "term": i,
            "term_mult": "M",
            "rate": round(0.0350 + (i * 0.001), 4)
        } for i in range(1, 4)])
    }

    os.makedirs(output_dir, exist_ok=True)
    files = []
    for fname, df in templates.items():
        path = os.path.join(output_dir, fname)
        df.to_excel(path, index=False, engine="openpyxl")
        files.append(path)

    return files


# ── FTP rate test data ────────────────────────────────────────────────────────

_RATE_CONFIGS = [
    ("SWAP_RATE",  1,  "M", 0.0350),
    ("SWAP_RATE",  3,  "M", 0.0365),
    ("SWAP_RATE",  6,  "M", 0.0380),
    ("SWAP_RATE", 12,  "M", 0.0400),
    ("LIBOR_USD",  1,  "M", 0.0520),
    ("LIBOR_USD",  3,  "M", 0.0535),
    ("LIBOR_USD",  6,  "M", 0.0550),
    ("LIBOR_USD", 12,  "M", 0.0570),
    ("BASE_RATE",  1,  "M", 0.0490),
    ("BASE_RATE",  3,  "M", 0.0490),
    ("BASE_RATE",  6,  "M", 0.0500),
    ("BASE_RATE", 12,  "M", 0.0510),
]


def generate_interest_rates(as_of_date=None):
    """Seed 30 days of approved RefInterestRate rows (3 codes × 4 tenors × 30 days)."""
    from app.models.ftp import RefInterestRate

    if as_of_date is None:
        as_of_date = date.today()

    count = 0
    for days_back in range(29, -1, -1):
        obs_date = as_of_date - timedelta(days=days_back)
        for code, term, mult, base in _RATE_CONFIGS:
            exists = RefInterestRate.query.filter_by(
                effective_date=obs_date,
                interest_rate_code=code,
                term=term,
                term_mult=mult,
            ).first()
            if exists:
                continue
            noise = random.uniform(-0.001, 0.001)
            db.session.add(RefInterestRate(
                effective_date=obs_date,
                interest_rate_code=code,
                term=term,
                term_mult=mult,
                rate=round(base + noise, 6),
                status="APPROVED",
                maker_id="system",
                checker_id="system",
            ))
            count += 1

    db.session.commit()
    return count


def generate_ftp_configs():
    """Seed FtpProductConfig for the 5 standard products if none exist."""
    from app.models.ftp import FtpProductConfig

    configs = [
        dict(product_code="PROD-LON", method="MOVING_AVG", rate_code="SWAP_RATE",
             term=5,  term_mult="Y", avg_period=3, avg_period_mult="M", is_active=True, created_by="system"),
        dict(product_code="PROD-MTG", method="MOVING_AVG", rate_code="SWAP_RATE",
             term=10, term_mult="Y", avg_period=3, avg_period_mult="M", is_active=True, created_by="system"),
        dict(product_code="PROD-DEP", method="MOVING_AVG", rate_code="LIBOR_USD",
             term=3,  term_mult="M", avg_period=1, avg_period_mult="M", is_active=True, created_by="system"),
        dict(product_code="PROD-SAV", method="MOVING_AVG", rate_code="LIBOR_USD",
             term=1,  term_mult="M", avg_period=1, avg_period_mult="M", is_active=True, created_by="system"),
        dict(product_code="PROD-CRD", method="MOVING_AVG", rate_code="BASE_RATE",
             term=12, term_mult="M", avg_period=1, avg_period_mult="M", is_active=True, created_by="system"),
    ]

    added = 0
    for cfg in configs:
        if not FtpProductConfig.query.filter_by(product_code=cfg["product_code"]).first():
            db.session.add(FtpProductConfig(**cfg))
            added += 1

    db.session.commit()
    return added


def generate_interest_rate_excel(output_dir: str) -> tuple[str, int]:
    """Generate interest_rate_testdata.xlsx (30 days × 3 codes × 4 tenors = 360 rows)."""
    as_of_date = date.today()
    rows = []
    for days_back in range(29, -1, -1):
        obs_date = as_of_date - timedelta(days=days_back)
        for code, term, mult, base in _RATE_CONFIGS:
            noise = random.uniform(-0.001, 0.001)
            rows.append({
                "effective_date": obs_date.isoformat(),
                "interest_rate_code": code,
                "term": term,
                "term_mult": mult,
                "rate": round(base + noise, 6),
            })

    df = pd.DataFrame(rows)
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "interest_rate_testdata.xlsx")
    df.to_excel(path, index=False, engine="openpyxl")
    return path, len(rows)


def seed_default_allocation_rules():
    """Seed two default allocation rules if they do not already exist.

    Rule 1 — Instrument to Management Instrument:
        proc_inst_data → fct_mgmt_instrument via RATIO on customer_id

    Rule 2 — GL to Management Ledger:
        proc_gl_data → fct_mgmt_ledger via STATIC pass-through on org_unit_id
    """
    from app.models.workflow import AllocationRule

    defaults = [
        dict(
            name="Default Instrument Allocation",
            description=(
                "Out-of-box rule: allocates proc_inst_data to fct_mgmt_instrument "
                "using customer-level ratios (ref_static_allocation). "
                "Emits DEBIT + CREDIT entries; financial_element rows produced per balance column."
            ),
            source_table="proc_inst_data",
            lookup_table="ref_static_allocation",
            output_table="fct_mgmt_instrument",
            allocation_method="RATIO",
            join_key="customer_id",
            entry_mode="BOTH",
            is_active=True,
            status="ACTIVE",
            created_by="system",
        ),
        dict(
            name="Default GL Allocation",
            description=(
                "Out-of-box rule: passes proc_gl_data through to fct_mgmt_ledger "
                "as a STATIC (no-split) allocation. "
                "Source org_unit_id is preserved on the output row."
            ),
            source_table="proc_gl_data",
            lookup_table="ref_static_allocation",
            output_table="fct_mgmt_ledger",
            allocation_method="STATIC",
            join_key="org_unit_id",
            entry_mode="DEBIT_ONLY",
            is_active=True,
            status="ACTIVE",
            created_by="system",
        ),
    ]

    added = 0
    for cfg in defaults:
        exists = AllocationRule.query.filter_by(name=cfg["name"]).first()
        if not exists:
            db.session.add(AllocationRule(**cfg))
            added += 1

    db.session.commit()
    return added
