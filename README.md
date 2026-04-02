# BankPFT — Management Allocation System

A prototype **Management Allocation System** that redistributes financial balances and income from a Legal/Booking level to a Management level using static allocation ratios. Built with Flask, SQLAlchemy, and SQLite.

## Features

| Module | Description |
|---|---|
| **Data Upload** | Excel/CSV upload for Instrument, GL, Allocation Ratio, and Org Reclassification data with column-level validation |
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

Allocation ratios are stored in `REF_STATIC_ALLOCATION` and linked by `customer_id`. Each customer's ratios must sum to 1.0 per allocation group. Org reclassifications are stored in `REF_ORG_RECLASS` as 1:1 org-to-org mappings (ratio always 1.0).

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
│   ├── allocation.py        # RefStaticAllocation, RefOrgReclass, FctMgmtLedger
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

## JSON vs Database — What Lives Where

The system separates **configuration** (JSON files, no code changes) from **runtime data** (database, created by users at runtime).

### Design Principle

```
JSON files  =  rules, column definitions, form options, engine settings  (HOW things work)
Database    =  uploaded data, workflow state, execution results           (WHAT happened)
```

### Upload Module

| Aspect | Source | Details |
|---|---|---|
| Data types (INSTRUMENT, GL, ALLOCATION, ORG_RECLASS) | **JSON** `upload_config.json` | Labels, descriptions, required/optional columns |
| Which validation rules run per type | **JSON** `upload_config.json` | `validation_rules` list per data type |
| Validation rule behavior | **JSON** `validation_rules.json` | Enabled, severity, stop_on_fail |
| Column casting & defaults | **JSON** `upload_config.json` | `column_mapping` per data type |
| Numeric range checks | **JSON** `upload_config.json` | `numeric_ranges` per column |
| Dimension lookup targets | **JSON** `upload_config.json` | `dimension_lookups` per column |
| Uploaded rows & batch status | **DB** `upload_batch`, `stg_*` | Created at runtime by user uploads |
| Maker/Checker workflow state | **DB** `upload_batch` | DRAFT → PENDING → APPROVED → PROCESSED |

**To add a new upload data type:** add an entry to `upload_config.json` — no code changes.

### Allocation Rule Module

| Aspect | Source | Details |
|---|---|---|
| Form dropdown options | **JSON** `rule_config.json` | Source/lookup/output tables, join keys |
| Default form selections | **JSON** `rule_config.json` | `defaults` section |
| User's chosen rule config | **DB** `allocation_rule` | `source_table`, `lookup_table`, `output_table`, `join_key` saved per rule |
| Rule active/inactive state | **DB** `allocation_rule` | `is_active`, `status` |

When a user creates a rule via the form, the dropdowns come from `rule_config.json`, but the selected values are **saved to the database**. Each rule can have different table/join combinations.

### Allocation Engine (Batch Execution)

| Aspect | Source | Details |
|---|---|---|
| Which tables and join key to use | **DB** `allocation_rule` | Engine reads `rule.source_table`, `rule.join_key`, etc. |
| Column definitions for each table | **JSON** `allocation_config.json` | `source_tables.{table}.columns`, `balance_columns`, etc. |
| Lookup table columns & filters | **JSON** `allocation_config.json` | `lookup_tables.{table}.ratio_column`, `status_filter` |
| Orphan handling defaults | **JSON** `allocation_config.json` | `default_ratio`, `target_org_from` |
| Batch execution results | **DB** `batch_run`, `fct_mgmt_ledger` | Created at runtime by engine |

**Engine flow:**
```
1. User clicks "Run Allocation" with rule_id
2. Engine loads AllocationRule from DB → gets source_table, join_key, etc.
3. Engine looks up column definitions in allocation_config.json for that table
4. Engine queries source data (e.g. proc_inst_data) and lookup data (e.g. ref_static_allocation)
5. Pandas join on the rule's join_key → apply ratio → write to fct_mgmt_ledger
```

**To add a new source table:** add its column config to `allocation_config.json` and its option to `rule_config.json`.

## Lookup Tables

The system supports multiple lookup tables that the allocation engine can join against:

| Lookup Table | Purpose | Join Key | Ratio |
|---|---|---|---|
| `ref_static_allocation` | Shred balances across orgs by customer-level ratios | `customer_id` | Variable (must sum to 1.0 per group) |
| `ref_org_reclass` | Reclassify one org unit to another (1:1 mapping) | `org_unit_id` | Always 1.0 |

Both tables follow the Maker/Checker workflow (DRAFT → PENDING → APPROVED) and are uploaded via the standard upload screen.

## JSON Configuration Files

### `app/config/upload_config.json`

Defines each upload data type (INSTRUMENT, GL, ALLOCATION, ORG_RECLASS) with:
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
- **lookup_tables** — selectable lookup tables (e.g. Static Allocation, Org Reclassification)
- **output_tables** — selectable output tables
- **join_keys** — selectable join keys (e.g. `customer_id`, `org_unit_id`, `product_code`)
- **defaults** — pre-selected values for each dropdown

All dropdowns in the "Create Rule" form are rendered from this file. Values must match keys in `allocation_config.json`.

### `app/config/allocation_config.json`

Controls the batch allocation engine with per-table column definitions:
- **source_tables** — keyed by table name, each with `columns`, `balance_columns`, `date_filter_column`, `account_id_column`
- **lookup_tables** — keyed by table name, each with `columns`, `ratio_column`, `id_column`, `target_org_column`, `status_filter`
- **output_tables** — keyed by table name (model reference)
- **join_keys** — available join keys with `available_in` list showing which source tables support them
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
