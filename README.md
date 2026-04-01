# BankPFT — Management Allocation System

A prototype **Management Allocation System** that redistributes financial balances and income from a Legal/Booking level to a Management level using static allocation ratios. Built with Flask, SQLAlchemy, and SQLite.

## Features

| Module | Description |
|---|---|
| **Data Upload** | Excel/CSV upload for Instrument, GL, and Allocation Ratio data with column-level validation |
| **Maker/Checker (4-Eyes)** | Upload workflow: DRAFT → PENDING → APPROVED → PROCESSED. Maker cannot approve their own submission |
| **Allocation Rules** | Configure source table, lookup table, output table, and join key. Rules are immediately active |
| **Batch Execution** | Run allocation rules against processed instrument data using Pandas-based "shredding" logic |
| **Reporting** | Dashboard, management ledger report, execution log, operations report, and database table browser |
| **Test Data Generator** | Generate master data, instrument data, GL data, and allocation ratio Excel files for testing |

## Architecture

```
Dimensions (Org Unit, Product, Customer, Account)
        ↓ validation
Staging (STG_INST_DATA, STG_GL_DATA)
        ↓ Maker/Checker approval
Processing (PROC_INST_DATA, PROC_GL_DATA)
        ↓ Allocation Engine (Pandas join + ratio shredding)
Result (FCT_MGMT_LEDGER)
```

Allocation ratios are stored in `REF_STATIC_ALLOCATION` and linked by `customer_id`. Each customer's ratios must sum to 1.0 per allocation group.

## Tech Stack

- **Backend:** Flask 3.0, SQLAlchemy 2.0, Pandas 2.1
- **Database:** SQLite (file-based, zero config)
- **Frontend:** Bootstrap 5.3 (CDN), Bootstrap Icons
- **Upload:** openpyxl for Excel parsing
- **Deployment:** Gunicorn, Docker

## Quick Start

### Local

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python run.py
```

Open http://localhost:5000

### Docker

```bash
docker compose up --build
```

## Project Structure

```
app/
├── __init__.py              # App factory
├── config.py                # Flask configuration
├── config/
│   ├── upload_config.json   # Upload validation & staging rules
│   └── allocation_config.json # Allocation engine settings
├── models/
│   ├── dimensions.py        # DimOrgUnit, DimProduct, DimCustomer, DimAccount
│   ├── staging.py           # StgInstData, ProcInstData, StgGlData, ProcGlData
│   ├── allocation.py        # RefStaticAllocation, FctMgmtLedger
│   └── workflow.py          # UploadBatch, AllocationRule, BatchRun
├── routes/
│   ├── dashboard.py         # Home dashboard
│   ├── upload.py            # Data upload with Maker/Checker
│   ├── rules.py             # Allocation rule CRUD
│   ├── batch.py             # Batch execution
│   ├── reports.py           # Reports & table browser
│   └── testdata.py          # Test data generation
├── services/
│   ├── __init__.py          # Maker/Checker state machine
│   ├── upload_service.py    # Config-driven file parsing & validation
│   ├── allocation_engine.py # Config-driven Pandas shredding engine
│   └── testdata_service.py  # Test data generators
└── templates/               # Jinja2 / Bootstrap 5 templates
```

## JSON Configuration

Business logic for uploads and allocation is driven by JSON config files — no code changes needed to adjust column mappings, validation rules, or engine behavior.

### `app/config/upload_config.json`

Controls per data type (INSTRUMENT, GL, ALLOCATION):
- **required_columns / optional_columns** — which columns must exist in the upload
- **unique_key** — column checked for duplicates (e.g. `account_id`)
- **dimension_lookups** — maps upload columns to dimension tables for referential integrity checks
- **column_mapping** — type casting rules (date/float/string) with defaults for optional fields
- **ratio_validation** — group-by keys, expected sum, and tolerance for allocation ratio checks

### `app/config/allocation_config.json`

Controls the batch allocation engine:
- **source** — table, columns, and date filter column
- **lookup** — table, status filter (`APPROVED`), and columns
- **join** — join key (`customer_id`) and join type (`left`)
- **output** — balance columns to apply ratios to, ratio column name
- **orphan_handling** — enabled flag, default ratio (1.0), target org source

## Usage Workflow

1. **Generate test data** — Go to `/testdata` and generate master data, then instrument data and allocation ratios
2. **Upload data** — Go to `/upload/new`, select data type, upload the Excel file. Validation runs automatically
3. **Approve uploads** — A different user reviews staged data and approves (4-Eyes enforcement)
4. **Create a rule** — Go to `/rules/new`, configure source → lookup → output mapping
5. **Run batch** — Go to `/batch`, select a rule and as-of date, execute the allocation
6. **View results** — Check the Management Ledger report and execution log under `/reports`

## Data Validation

Uploads are validated using a single generic engine driven by `upload_config.json`:

- **Required columns** — checked per data type from config
- **Null checks** — on all required columns
- **Unique key** — duplicate detection on configured key column
- **Dimension lookups** — referential integrity against configured dimension tables
- **Ratio validation** — group-by sum check with configurable tolerance (allocation type only)

To add a new data type, add an entry to `upload_config.json` — no code changes required.

## Database

SQLite database is created automatically at `instance/bankpft.db` on first run. Tables are auto-created by SQLAlchemy. Delete the file to reset.

## License

Prototype / Demo — not for production use.
