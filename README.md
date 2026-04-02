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
│   ├── upload_config.json     # Upload types, columns, validation rule lists
│   ├── validation_rules.json  # Validation rule definitions (enabled/severity/stop)
│   ├── rule_config.json       # Allocation rule form options & defaults
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

Business logic for uploads, validation, allocation rules, and the allocation engine is driven by **4 JSON config files** — no code changes needed to add data types, toggle validation rules, or adjust engine behavior.

### `app/config/upload_config.json`

Defines each upload data type (INSTRUMENT, GL, ALLOCATION) with:
- **label / description** — display name and tooltip shown in the upload form
- **required_columns / optional_columns** — which columns must exist in the upload
- **unique_key** — column checked for duplicates (e.g. `account_id`)
- **dimension_lookups** — maps upload columns to dimension tables for referential integrity checks
- **column_mapping** — type casting rules (date/float/string) with defaults for optional fields
- **numeric_ranges** — per-column min/max bounds (e.g. `ratio: {min: 0, max: 1}`)
- **ratio_validation** — group-by keys, expected sum, and tolerance for allocation ratio checks
- **validation_rules** — ordered list of rule IDs to run for this data type (references `validation_rules.json`)

The upload form dropdown and expected-columns display are rendered dynamically from this file.

### `app/config/validation_rules.json`

Defines the available validation rule types with per-rule settings:
- **id / name / description** — rule identifier and display metadata
- **enabled** — toggle a rule on/off without removing it from data types
- **severity** — `error` (blocks approval) or `warning` (informational)
- **stop_on_fail** — halt remaining checks when this rule fails
- **max_errors_shown** — cap on error messages returned per validation run

Built-in rules: `required_columns`, `null_check`, `unique_key`, `dimension_lookup`, `ratio_sum`, `numeric_range`.

### `app/config/rule_config.json`

Drives the allocation rule creation form:
- **source_tables** — selectable source tables (value/label pairs)
- **lookup_tables** — selectable lookup tables
- **output_tables** — selectable output tables
- **join_keys** — selectable join keys (e.g. `customer_id`, `org_unit_id`, `product_code`)
- **defaults** — pre-selected values for each dropdown

All dropdowns in the "Create Rule" form are rendered from this file.

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

Uploads are validated by a config-driven engine. Each data type declares which rules to run (in `upload_config.json`), and each rule's behavior is defined in `validation_rules.json`.

| Rule ID | Description | Configurable |
|---|---|---|
| `required_columns` | Checks all required columns exist | Column list per type |
| `null_check` | Detects nulls in required columns | Enabled/disabled |
| `unique_key` | Duplicate detection on key column | Key column per type |
| `dimension_lookup` | Referential integrity vs dimension tables | Column→table mapping |
| `ratio_sum` | Group-by sum check with tolerance | Group keys, expected sum, tolerance |
| `numeric_range` | Per-column min/max bounds | Min/max per column |

Each rule can be independently **enabled/disabled**, assigned a **severity** (error vs warning), and configured to **stop on failure**.

To add a new data type: add an entry to `upload_config.json` with its `validation_rules` list — no code changes required.
To add a new validation rule: define it in `validation_rules.json` and implement the check in `_run_validation_rule()`.

## Database

SQLite database is created automatically at `instance/bankpft.db` on first run. Tables are auto-created by SQLAlchemy. Delete the file to reset.

## License

Prototype / Demo — not for production use.
