# BankPFT — Management Allocation System

A prototype **Management Allocation System** that redistributes financial balances and income from a Legal/Booking level to a Management level using static allocation ratios. Built with Flask, SQLAlchemy, and SQLite.

## Features

| Module | Description |
|---|---|
| **User & Group Management** | User login, group-based roles (Maker/Checker/Admin). Admin UI for creating users, groups, and assigning permissions |
| **Data Upload** | Excel/CSV upload for Instrument, GL, Allocation Ratio, and Org Reclassification data with column-level validation |
| **Maker/Checker (4-Eyes)** | Upload workflow: DRAFT → PENDING → APPROVED → PROCESSED. Group-based permissions enforce who can make vs check. Maker cannot approve their own submission |
| **Allocation Rules** | Configure source/lookup/output tables, join key, data filters, per-dimension source member filters (including account/GL account dimension), separate DEBIT and CREDIT dimension mapping (same-as-source / lookup / fixed), and entry mode (BOTH / DEBIT only / CREDIT only). Rules can be created, edited, or imported from JSON |
| **Batch Execution** | Run allocation rules against processed instrument data using Pandas-based "shredding" logic. FTP runs can also be triggered from the same batch page |
| **Fund Transfer Pricing** | FTP engine calculates `base_rate` (moving-average over configurable lookback period) and `cost_of_fund` (balance × base_rate × actual/actual day count) per instrument. Configurable per product code. Interest rates uploaded via the standard Maker/Checker workflow |
| **Reporting** | Dashboard, management ledger report, execution log, operations report, and database table browser with admin-only inline edit/delete |
| **Data File Management** | JSON-configured fixed-length and delimited (CSV/pipe/tab) file import from inbox folder and export to outbox. Per-file rule JSONs (`import_loan.json`, `export_inst_proc.json`, etc.) with a full transform expression sandbox (substring, concat, pad, conditional, type conversion, null-default) |
| **REST API** | HTTP Basic Auth API at `/api/v1/` — trigger data file imports/exports, run allocation batches, run FTP batches, and poll status. All responses JSON |
| **Security** | Login-required on all routes, admin guard on sensitive operations, no debug stack traces in production, friendly 404/500 error pages |
| **PWA** | Installable as a standalone app (no browser address bar) via web app manifest |
| **Test Data Generator** | Generate master data, instrument data, GL data, allocation ratio, and interest rate Excel files for testing. Seed FTP product configs in one click |

## Architecture

```
Dimensions (Org Unit, Product, Customer, Account)
        ↓ validation
Staging (STG_INST_DATA, STG_GL_DATA, REF_INTEREST_RATE)
        ↓ Maker/Checker approval
Processing (PROC_INST_DATA, PROC_GL_DATA)
        ↓ Allocation Engine (Pandas join + ratio shredding)
        ↓ per-dimension source filter  →  join  →  DEBIT dim mapping (output_dim_json)
                                                   CREDIT dim mapping (credit_dim_json)
Result  FCT_MGMT_INSTRUMENT  (entry_mode: BOTH | DEBIT_ONLY | CREDIT_ONLY, instrument-level)
        FCT_MGMT_LEDGER      (ledger output)

FTP Engine (separate)
        REF_INTEREST_RATE (approved) → moving-average lookup → base_rate per instrument
        cost_of_fund = balance × base_rate × (days_in_month / days_in_year)
        Results written back to PROC_INST_DATA.base_rate / PROC_INST_DATA.cost_of_fund
```

Allocation ratios are stored in `REF_STATIC_ALLOCATION` and linked by `customer_id`. Each customer's ratios must sum to 1.0 per allocation group. Org reclassifications are stored in `REF_ORG_RECLASS` as 1:1 org-to-org mappings (ratio always 1.0).

## Tech Stack

- **Backend:** Flask 3.0, SQLAlchemy 2.0, Pandas 2.1, Flask-Login 0.6
- **Database:** SQLite (file-based, zero config)
- **Frontend:** Bootstrap 5.3 (CDN), Bootstrap Icons
- **Auth:** Flask-Login with group-based role permissions
- **Upload:** openpyxl for Excel parsing
- **Deployment:** Gunicorn, Docker

## Quick Start

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | `dev-secret-change-in-production` | Flask session signing key — **set this in production** |
| `DATABASE_URL` | `sqlite:///instance/bankpft.db` | SQLAlchemy connection string |
| `FLASK_DEBUG` | `0` | Set to `1` to enable debug mode (development only) |

### Local (recommended — `start.sh`)

```bash
# Development server (auto-creates venv, installs deps)
./start.sh

# or explicitly:
./start.sh dev

# Production (Gunicorn daemon, 4 workers)
./start.sh prod

# Stop Gunicorn daemon
./start.sh stop
```

Open http://localhost:5000

### Manual (without start.sh)

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python run.py
```

Open http://localhost:5000

**Default accounts** (password = username):

| Username | Role | Permissions |
|---|---|---|
| `admin` | Administrator | Make + Check + Admin |
| `maker1` | Maker | Create and submit uploads |
| `checker1` | Checker | Approve/reject uploads |

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
│   ├── filter_config.json     # Filterable columns & operators per source table
│   ├── allocation_config.json # Allocation engine settings
│   ├── datafile_config.json   # Data file global settings (inbox/outbox paths)
│   └── datafile/              # Per-file import & export rule JSONs
│       ├── import_loan.json       # example: fixed-length loan file → stg_inst_data
│       ├── import_inst_csv.json   # example: CSV instrument file
│       ├── export_inst_proc.json  # example: fixed-length export
│       └── ...                    # one JSON per import or export rule
├── models/
│   ├── auth.py              # User, Group, UserGroup (login & role management)
│   ├── dimensions.py        # DimOrgUnit, DimProduct, DimCustomer, DimAccount
│   ├── staging.py           # StgInstData, ProcInstData, StgGlData, ProcGlData
│   ├── allocation.py        # RefStaticAllocation, RefOrgReclass, FctMgmtLedger, FctMgmtInstrument
│   ├── ftp.py               # RefInterestRate, FtpProductConfig, FtpRun
│   ├── datafile.py          # DataFileBatch (import/export run history)
│   └── workflow.py          # UploadBatch, AllocationRule, BatchRun
├── routes/
│   ├── auth.py              # Login, logout, change password
│   ├── admin.py             # User & group management (admin only)
│   ├── dashboard.py         # Home dashboard
│   ├── upload.py            # Data upload with Maker/Checker
│   ├── rules.py             # Allocation rule CRUD + JSON import
│   ├── batch.py             # Batch execution (Allocation + FTP)
│   ├── ftp.py               # FTP dashboard, config CRUD, rate browser, run detail
│   ├── reports.py           # Reports & table browser
│   ├── datafile.py          # Data File Management UI (inbox/outbox, batch history)
│   ├── api.py               # REST API v1 (HTTP Basic Auth, JSON)
│   └── testdata.py          # Test data generation
├── services/
│   ├── __init__.py          # Maker/Checker state machine (group-aware)
│   ├── upload_service.py    # Config-driven file parsing & validation
│   ├── allocation_engine.py # Config-driven Pandas shredding engine
│   ├── ftp_engine.py        # FTP moving-average engine (run_ftp)
│   ├── datafile_service.py  # Fixed-length & delimited import/export engine
│   └── testdata_service.py  # Test data generators (incl. FTP rate seeding)
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
| Filter field/operator options | **JSON** `filter_config.json` | Available columns & operators per source table |
| User's chosen rule config | **DB** `allocation_rule` | `source_table`, `lookup_table`, `output_table`, `join_key` saved per rule |
| User's data filter conditions | **DB** `allocation_rule.filter_json` | JSON: `{"logic":"AND","conditions":[{"field":"..","operator":"..","value":".."}]}` || Source dimension member filters | **DB** `allocation_rule.source_dim_json` | Per-dimension: `{"org_unit_id":{"mode":"specific","members":["OU1"]}}` |
| Debit dimension mapping | **DB** `allocation_rule.output_dim_json` | Per-dimension (incl. `account_id`/`gl_account`): `{"account_id":{"mode":"same_as_source"},"org_unit_id":{"mode":"lookup","lookup_column":"target_org_unit_id"}}` |
| Credit dimension mapping | **DB** `allocation_rule.credit_dim_json` | Per-dimension (incl. `account_id`/`gl_account`). Omit to default all dims to `same_as_source` |
| Entry mode | **DB** `allocation_rule.entry_mode` | `BOTH` (default) = DEBIT + CREDIT, `DEBIT_ONLY`, or `CREDIT_ONLY` || Rule active/inactive state | **DB** `allocation_rule` | `is_active`, `status` |

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
1. Load AllocationRule from DB → source_table, join_key, filter_json, source_dim_json, output_dim_json, credit_dim_json, entry_mode
2. Look up column definitions in allocation_config.json for each table
3. Query source data (e.g. proc_inst_data) → apply filter_json → apply source_dim_json member filters
4. Query lookup data (e.g. ref_static_allocation)
5. Pandas LEFT JOIN on rule's join_key
6. For each matched row: compute allocated_balance = source × ratio
7. Resolve DEBIT output dimensions per output_dim_json (same-as-source / lookup column / fixed value)
8. If entry_mode ∈ {BOTH, DEBIT_ONLY}: write DEBIT entry to output table (fct_mgmt_instrument or fct_mgmt_ledger)
9. If entry_mode ∈ {BOTH, CREDIT_ONLY}: resolve CREDIT dimensions per credit_dim_json (defaults to same-as-source); write CREDIT entry (negative balance)
10. Orphan rows (no lookup match) → DEBIT only at source org (default_ratio from config)
```

**To add a new source table:** add its column config to `allocation_config.json` and its option to `rule_config.json`.

## Lookup Tables

The system supports multiple lookup tables that the allocation engine can join against:

| Lookup Table | Purpose | Join Key | Ratio |
|---|---|---|---|
| `ref_static_allocation` | Shred balances across orgs by customer-level ratios | `customer_id` | Variable (must sum to 1.0 per group) |
| `ref_org_reclass` | Reclassify one org unit to another (1:1 mapping) | `org_unit_id` | Always 1.0 |

## Fund Transfer Pricing (FTP)

The FTP engine is independent of the allocation engine and operates on `proc_inst_data` directly.

### Data Model

| Table | Purpose |
|---|---|
| `ref_interest_rate` | Uploaded rate curves (Maker/Checker approved). Columns: `effective_date`, `interest_rate_code`, `term`, `term_mult`, `rate` |
| `ftp_product_config` | Per-product FTP settings: method, rate code, tenor (term+mult), lookback window (avg_period+mult) |
| `ftp_run` | Execution log: as_of_date, status, instruments processed/matched/skipped |

### Calculation Method: MOVING_AVG

```
1. For the instrument's product_code, look up FtpProductConfig (rate_code, term, term_mult, avg_period, avg_period_mult)
2. Compute lookback_start = as_of_date − avg_period × avg_period_mult
3. Query ref_interest_rate WHERE interest_rate_code=rate_code AND term=term AND term_mult=term_mult
   AND effective_date BETWEEN lookback_start AND as_of_date AND status='APPROVED'
4. base_rate = simple average of those rate values
5. days_in_month = calendar days in the as_of_date's month
6. days_in_year  = 366 if leap year else 365
7. cost_of_fund  = balance × base_rate × (days_in_month / days_in_year)
8. Write base_rate and cost_of_fund back to proc_inst_data
```

### FTP Upload Type

Interest rates are uploaded via the standard upload screen using **Data Type: Interest Rate**. The upload is validated (column checks, date cast) and follows the DRAFT → PENDING → APPROVED workflow before the FTP engine can use the rates.

### FTP Configuration (`/ftp/config`)

| Field | Example | Description |
|---|---|---|
| Product Code | `PROD-LON` | Must match a value in `dim_product` |
| Method | `MOVING_AVG` | Currently the only supported method |
| Rate Code | `SWAP_RATE` | Must match `interest_rate_code` in the rate table |
| Term / Term Mult | `5 / Y` | Tenor point to use from the rate curve |
| Avg Period / Mult | `3 / M` | Length of the moving-average lookback window |

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

### `app/config/filter_config.json`

Defines the data filter editor used in allocation rules:
- **operators** — available operators grouped by data type (`string`, `float`, `date`)
  - String: `eq`, `neq`, `in`, `not_in`, `contains`, `starts_with`
  - Float: `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `between`
  - Date: `eq`, `gt` (after), `lt` (before), `between`
- **filterable_columns** — per source table, lists which columns can be filtered with their label and data type

The filter editor dynamically updates when the source table changes — only columns belonging to the selected table are shown.

Filter conditions are stored as JSON in `allocation_rule.filter_json` and applied by the engine as Pandas DataFrame conditions before the join step.

### `app/config/allocation_config.json`

Controls the batch allocation engine with per-table column definitions:
- **source_tables** — keyed by table name, each with `columns`, `balance_columns`, `date_filter_column`, `account_id_column`
- **lookup_tables** — keyed by table name, each with `columns`, `ratio_column`, `id_column`, `target_org_column`, `status_filter`
- **output_tables** — keyed by table name (model reference)
- **join_keys** — available join keys with `available_in` list showing which source tables support them
- **orphan_handling** — enabled flag, default ratio (1.0), target org source

## User & Group Management

Authentication and authorization is handled via Flask-Login with group-based permissions.

### Groups

Each group has three permission flags:

| Permission | Grants |
|---|---|
| **Can Make** | Create uploads, submit for review, create rules, run batches |
| **Can Check** | Approve or reject uploads (4-Eyes enforcement) |
| **Admin** | Manage users and groups via `/admin` |

A user can belong to multiple groups. Effective permissions are the union of all group permissions.

### Default Groups

| Group | Can Make | Can Check | Admin |
|---|---|---|---|
| Makers | ✓ | | |
| Checkers | | ✓ | |
| Admins | ✓ | ✓ | ✓ |

### Admin Pages

- `/admin/users` — Create users, assign to groups, enable/disable, reset passwords
- `/admin/groups` — Create groups, configure permission flags

All routes require login (`@login_required`). Admin routes additionally check group membership.

## Usage Workflow

1. **Login** — Sign in at `/auth/login` (default accounts: admin/maker1/checker1, password = username)
2. **Generate test data** — Go to `/testdata` and generate master data, then instrument data and allocation ratios
3. **Upload data** — Go to `/upload/new`, select data type, upload the Excel file. Validation runs automatically
4. **Approve uploads** — Log in as a Checker user (different from maker) to approve (4-Eyes enforcement with group permission check)
5. **Create a rule** — Go to `/rules/new`, configure source → lookup → output mapping, and optionally add data filters
6. **Run batch** — Go to `/batch`, select a rule and as-of date, execute the allocation (filters are applied automatically)
7. **View results** — Check the Management Ledger report and execution log under `/reports`

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

## Output Tables

| Table | Purpose |
|---|---|
| `fct_mgmt_instrument` | Instrument-level allocation output — DEBIT + CREDIT offset entries (recommended default) |
| `fct_mgmt_ledger` | Legacy ledger output — retains backward compatibility |

Both tables share the same schema, with `entry_type` column indicating `DEBIT` or `CREDIT`.

## Allocation Rule JSON Import

Rules can be defined as JSON and imported via `/rules/import`. This allows batch setup, version control of rule configurations, and sharing between environments.

**Minimum valid rule JSON:**
```json
{"name": "My Rule"}
```

**Full schema:**
```json
{
  "name": "Customer Shred Q1",
  "description": "Shred instrument balances by customer ratio",
  "source_table": "proc_inst_data",
  "lookup_table": "ref_static_allocation",
  "output_table": "fct_mgmt_instrument",
  "join_key": "customer_id",
  "generate_offset": true,
  "offset_account": "GL_OFFSET_9000",
  "filter_json": {
    "logic": "AND",
    "conditions": [{"field": "product_code", "operator": "in", "value": "LOAN,DEPOSIT"}]
  },
  "source_dim_json": {
    "org_unit_id":  {"mode": "all"},
    "product_code": {"mode": "specific", "members": ["LOAN", "DEPOSIT"]},
    "customer_id":  {"mode": "all"}
  },
  "output_dim_json": {
    "org_unit_id":  {"mode": "lookup",         "lookup_column": "target_org_unit_id"},
    "product_code": {"mode": "same_as_source"},
    "customer_id":  {"mode": "same_as_source"}
  },
  "credit_dim_json": {
    "org_unit_id":  {"mode": "same_as_source"},
    "product_code": {"mode": "same_as_source"},
    "customer_id":  {"mode": "same_as_source"}
  }
}
```

## Data File Management

A JSON-configured batch file I/O engine that reads from an **inbox** folder and writes to an **outbox** folder, independent of the Excel upload workflow.

### File Format Support

| Format | Config key | Description |
|---|---|---|
| Fixed-length | `"type": "fixed_length"` | Slice fields by `start` / `length` positions |
| Delimited (CSV, pipe, tab, custom) | `"type": "delimited"` | Split by `delimiter`, map by column index or header name |

### Per-file Rule JSON

Each import or export is defined in its own JSON file under `app/config/datafile/`. The service scans the directory at startup.

**Import example** (`app/config/datafile/import_loan.json`):
```json
{
  "operation": "import",
  "format_id": "LOAN_FIXED",
  "name": "Loan File — Fixed Length",
  "type": "fixed_length",
  "record_length": 120,
  "target_table": "stg_inst_data",
  "fields": [
    { "name": "account_id",   "start": 0,  "length": 12, "type": "string" },
    { "name": "branch_code",  "start": 12, "length": 4,  "type": "string",
      "transform": "concat('BR', lpad(value, 4, '0'))" },
    { "name": "balance",      "start": 16, "length": 14, "type": "decimal",
      "transform": "to_float(value) / 100" },
    { "name": "maturity_date","start": 30, "length": 8,  "type": "date",
      "date_format": "YYYYMMDD" }
  ]
}
```

**Export example** (`app/config/datafile/export_inst_proc.json`):
```json
{
  "operation": "export",
  "export_id": "INST_PROC_EXPORT",
  "name": "Processed Instruments Export",
  "source_table": "proc_inst_data",
  "format": "fixed_length",
  "fields": [
    { "name": "account_id", "length": 20, "align": "left",  "pad": " " },
    { "name": "balance",    "length": 18, "align": "right", "pad": " " }
  ]
}
```

### Transform Expression Sandbox

Field transforms are safe-eval expressions. Available functions:

| Category | Functions |
|---|---|
| String | `upper`, `lower`, `trim`, `ltrim`, `rtrim`, `left`, `right`, `substr`, `lpad`, `rpad`, `replace`, `concat`, `startswith`, `endswith`, `contains` |
| Conditional | `iif(cond, a, b)`, inline `a if cond else b`, `nvl(val, default)`, `coalesce(a, b, ...)` |
| Conversion | `to_float(v)`, `to_int(v)` |
| Slice | `value[0:5]` |

**Examples:**

| Transform expression | Input → Output |
|---|---|
| `concat('BR', lpad(value, 4, '0'))` | `'12'` → `'BR0012'` |
| `to_float(value) / 100` | `'25000000'` → `250000.0` |
| `upper(trim(value))` | `' loan '` → `'LOAN'` |
| `'DEBIT' if to_float(value) > 0 else 'CREDIT'` | `'500'` → `'DEBIT'` |
| `nvl(value, 'UNKNOWN')` | `''` → `'UNKNOWN'` |
| `'HIGH' if to_int(value) >= 80 else ('MED' if to_int(value) >= 50 else 'LOW')` | `'90'` → `'HIGH'` |
| `'Y' if upper(trim(value)) in ['LOAN','MTG'] else 'N'` | `'loan'` → `'Y'` |
| `replace(value, ',', '')` | `'1,234,567'` → `'1234567'` |
| `round(to_float(replace(value, ',', '')) / 100, 2)` | `'1,234,567'` → `12345.67` |
| `value[0:8]` | `'20260101extra'` → `'20260101'` |
| `concat(left(value, 4), '****', right(value, 4))` | `'ACC-12345678'` → `'ACC-****5678'` |

Full annotated demo files for every transform category:

| File | Description |
|---|---|
| `app/config/datafile/import_transform_demo.json` | 10 import categories (raw string `value` from file) |
| `app/config/datafile/export_transform_demo.json` | 9 export categories (Python DB value — str/float/date/None) |

Each field in those files has a `_comment` with an input → output example. Copy any block directly into a production rule.

### UI

- **`/datafile/`** — batch history with status, row counts, and error summaries
- **`/datafile/<batch_id>`** — full batch detail with per-row error list

---

## REST API

All endpoints are mounted at `/api/v1/` and require **HTTP Basic Auth** using existing user credentials.

```bash
curl -u admin:admin http://localhost:5000/api/v1/datafile/formats
```

### Authentication

Every request must include an `Authorization: Basic <base64(user:pass)>` header.
Invalid credentials return `401` with a `WWW-Authenticate` challenge.

### Data File Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/datafile/formats` | List available import format IDs |
| `GET` | `/api/v1/datafile/exports` | List available export config IDs |
| `POST` | `/api/v1/datafile/import` | Trigger an import run |
| `POST` | `/api/v1/datafile/export` | Trigger an export run |
| `GET` | `/api/v1/datafile/batch/<id>` | Get import/export batch status |

#### Import — curl examples (one per format)

```bash
# List formats first to see available format_ids
curl -u admin:admin http://localhost:5000/api/v1/datafile/formats

# Fixed-length loan file
curl -u admin:admin -X POST -H 'Content-Type: application/json' \
  -d '{"format_id": "LOAN_FIXED", "filename": "loan.dat"}' \
  http://localhost:5000/api/v1/datafile/import

# Fixed-length instrument file
curl -u admin:admin -X POST -H 'Content-Type: application/json' \
  -d '{"format_id": "INST_FIXED", "filename": "instruments_20260101.dat"}' \
  http://localhost:5000/api/v1/datafile/import

# CSV instrument file
curl -u admin:admin -X POST -H 'Content-Type: application/json' \
  -d '{"format_id": "INST_CSV", "filename": "instruments_20260101.csv"}' \
  http://localhost:5000/api/v1/datafile/import

# Fixed-length GL file
curl -u admin:admin -X POST -H 'Content-Type: application/json' \
  -d '{"format_id": "GL_FIXED", "filename": "gl_20260101.dat"}' \
  http://localhost:5000/api/v1/datafile/import

# Pipe-delimited GL file (header-mapped)
curl -u admin:admin -X POST -H 'Content-Type: application/json' \
  -d '{"format_id": "GL_PIPE", "filename": "gl_20260101.txt"}' \
  http://localhost:5000/api/v1/datafile/import
```

#### Export — curl examples (one per export)

```bash
# List exports first to see available export_ids
curl -u admin:admin http://localhost:5000/api/v1/datafile/exports

# Fixed-length processed instruments export
curl -u admin:admin -X POST -H 'Content-Type: application/json' \
  -d '{"export_id": "INST_PROC_EXPORT", "as_of_date": "2026-01-01"}' \
  http://localhost:5000/api/v1/datafile/export

# CSV instruments export
curl -u admin:admin -X POST -H 'Content-Type: application/json' \
  -d '{"export_id": "INST_CSV_EXPORT", "as_of_date": "2026-01-01"}' \
  http://localhost:5000/api/v1/datafile/export

# Allocation results export (DEBIT entries only)
curl -u admin:admin -X POST -H 'Content-Type: application/json' \
  -d '{"export_id": "ALLOC_RESULT_EXPORT", "as_of_date": "2026-01-01"}' \
  http://localhost:5000/api/v1/datafile/export

# Omit as_of_date to default to today
curl -u admin:admin -X POST -H 'Content-Type: application/json' \
  -d '{"export_id": "INST_PROC_EXPORT"}' \
  http://localhost:5000/api/v1/datafile/export
```

#### Python examples

```python
import requests

BASE = "http://localhost:5000"
AUTH = ("admin", "admin")

# Import a CSV instrument file
r = requests.post(f"{BASE}/api/v1/datafile/import",
                  json={"format_id": "INST_CSV", "filename": "instruments_20260101.csv"},
                  auth=AUTH)
batch = r.json()
print(batch["status"], "rows:", batch["row_count"], "errors:", batch["error_count"])

# Poll batch status
import requests
status = requests.get(f"{BASE}/api/v1/datafile/batch/{batch['batch_id']}", auth=AUTH).json()
if status["error_count"] > 0:
    for err in status["errors"]:
        print(f"  Row {err['row']} | {err['field']} = '{err['raw_value']}' → {err['error']}")

# Export CSV instruments for a specific date
r = requests.post(f"{BASE}/api/v1/datafile/export",
                  json={"export_id": "INST_CSV_EXPORT", "as_of_date": "2026-01-01"},
                  auth=AUTH)
result = r.json()
print(result["status"], "rows:", result["row_count"], "file:", result["filename"])
```

**Response (import/export):**
```json
{
  "batch_id": "21ef93cb-b7af-4073-8c2f-8417b2a40f8d",
  "operation": "import",
  "format_id": "LOAN_FIXED",
  "format_name": "Loan Data — Fixed Length",
  "filename": "loan.dat",
  "target_table": "stg_inst_data",
  "status": "COMPLETED",
  "row_count": 3,
  "error_count": 0,
  "errors": [],
  "error_message": null,
  "run_by": "admin",
  "started_at": "2026-01-01T00:00:00Z",
  "completed_at": "2026-01-01T00:00:01Z"
}
```

### Allocation Batch Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/batch/rules` | List active allocation rules |
| `POST` | `/api/v1/batch/allocation` | Run an allocation batch |
| `GET` | `/api/v1/batch/allocation/<id>` | Get allocation batch status |
| `POST` | `/api/v1/batch/ftp` | Run the FTP calculation engine |
| `GET` | `/api/v1/batch/ftp/<id>` | Get FTP run status |

**POST `/api/v1/batch/allocation`**
```json
{ "rule_id": 1, "as_of_date": "2026-01-01" }
```

**POST `/api/v1/batch/ftp`**
```json
{ "as_of_date": "2026-01-01" }
```

**Response (allocation batch):**
```json
{
  "batch_id": "...",
  "rule_id": 1,
  "as_of_date": "2026-01-01",
  "status": "COMPLETED",
  "source_row_count": 120,
  "output_row_count": 240,
  "orphan_count": 0,
  "source_total": 5000000.0,
  "output_total": 5000000.0,
  "started_at": "2026-01-01T00:00:00Z",
  "completed_at": "2026-01-01T00:00:02Z"
}
```

### HTTP Status Codes

| Code | Meaning |
|---|---|
| `200` | Success |
| `400` | Bad request (missing/invalid body field) |
| `401` | Unauthorized (missing or wrong credentials) |
| `404` | Resource not found |
| `422` | Run triggered but completed with errors (check `error_message` / `errors`) |

---

## start.sh Reference

| Command | Description |
|---|---|
| `./start.sh` or `./start.sh dev` | Flask development server with auto-reload |
| `./start.sh prod` | Gunicorn daemon (4 workers, logs to `bankpft.log`) |
| `./start.sh stop` | Stop a running Gunicorn daemon |
| `./start.sh docker` | Build and start via Docker Compose |

Environment variable: `WORKERS=8 ./start.sh prod` overrides the default 4 Gunicorn workers.



## License

Prototype / Demo — not for production use.
