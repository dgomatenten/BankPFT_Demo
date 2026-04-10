# BankPFT — Management Allocation System

A prototype **Management Allocation System** that redistributes financial balances and income from a Legal/Booking level to a Management level using static allocation ratios. Built with Flask, SQLAlchemy, and PostgreSQL.

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [JSON vs Database — What Lives Where](#json-vs-database--what-lives-where)
- [Lookup Tables](#lookup-tables)
- [Fund Transfer Pricing (FTP)](#fund-transfer-pricing-ftp)
- [JSON Configuration Files](#json-configuration-files)
- [User & Group Management](#user--group-management)
- [Usage Workflow](#usage-workflow)
- [Data Validation](#data-validation)
- [Output Tables](#output-tables)
- [Allocation Rule JSON Import](#allocation-rule-json-import)
- [FTP Product Config JSON Import](#ftp-product-config-json-import)
- [Data File Management](#data-file-management)
- [REST API](#rest-api)
- [Test Framework](#test-framework)
- [start.sh Reference](#startsh-reference)
- **Implementation Considerations**
  - [Authentication (Azure AD / Entra ID)](#authentication-implementation-consideration)
  - [Batch Parallel Run & Async UI](#batch-parallel-run--async-ui-implementation-consideration)
  - [Stored Procedure Framework](#stored-procedure-implementation-consideration)
  - [Custom Stored Procedure Batch Runner](#custom-stored-procedure-batch-runner)
  - [Logging Framework](#logging-framework--implementation-consideration)
  - [Exception & Error Handling Framework](#exception--error-handling-framework--implementation-consideration)
- [AI Development & Copilot Usage](#ai-development--copilot-usage)
- [License](#license)

---

## Features

| Module | Description |
|---|---|
| **User & Group Management** | User login, group-based roles (Maker/Checker/Admin). Admin UI for creating users, groups, and assigning permissions |
| **Manual Data Load** | Excel/CSV upload for Instrument, GL, Allocation Ratio, Org Reclassification, Static Distribution, and Static Allocation data with column-level validation. Accessible under the **Data Management** sidebar group |
| **Maker/Checker (4-Eyes)** | Upload workflow: DRAFT → PENDING → APPROVED → PROCESSED. Group-based permissions enforce who can make vs check. Maker cannot approve their own submission. On approval, configurable **post-approval actions** run automatically (execute allocation rule IDs or dispatch a stored procedure via `sp_runner`) |
| **Allocation Rules** | Configure source/lookup/output tables, join key, **allocation method** (Ratio-Based / Static Distribution / Static Allocation), **distribution driver** (named sub-table within `ref_static_distribution`), data filters, per-dimension source member filters (including account/GL account dimension), separate DEBIT and CREDIT dimension mapping (same-as-source / lookup / fixed), and entry mode (BOTH / DEBIT only / CREDIT only). Rules can be created, edited, or imported from JSON |
| **FTP Product Config Import** | FTP product configurations can be imported in bulk from a JSON file or pasted JSON. Supports a single config object or an array. If a `product_code` already exists its configuration is updated in-place. Available via `/ftp/config/import` (UI) and `POST /api/v1/ftp/config/import` (REST API) |
| **Batch Execution** | Multi-task batch definitions group allocation rules, FTP runs, data file imports/exports, and custom stored procedure calls into a single orchestrated run. Execution is **asynchronous** and non-blocking, allowing the UI to remain responsive while batches run in background threads. Features real-time status polling and live log streaming directly on the execution detail page. |
| **Fund Transfer Pricing** | Multi-component FTP engine calculates **COF**, **LP**, **CLP**, and **BUF** (Buffer Asset Cost) independently per instrument. Uses a `Model → Rule → Process` architecture where each rule targets a specific component with its own rate curve. |
| **Reporting** | Dashboard, management ledger report, execution log, operations report, and database table browser with admin-only inline edit/delete |
| **Data File Management** | JSON-configured fixed-length and delimited (CSV/pipe/tab) file import from inbox folder and export to outbox. Per-file rule JSONs (`import_loan.json`, `export_inst_proc.json`, etc.) with a full transform expression sandbox (substring, concat, pad, conditional, type conversion, null-default). Accessible under the **Data Management** sidebar group |
| **REST API** | HTTP Basic Auth API at `/api/v1/` — trigger data file imports/exports, run allocation batches, run FTP batches, run multi-task batch definitions, import allocation rules and FTP configs from JSON, and poll status. All responses JSON |
| **Security** | Login-required on all routes, admin guard on sensitive operations, no debug stack traces in production, friendly 404/500 error pages |
| **PWA** | Installable as a standalone app (no browser address bar) via web app manifest |
| **Test Data Generator** | Generate master data, instrument data, GL data, allocation ratio, and interest rate Excel files for testing. Seed FTP product configs in one click |
| **Regression Test Framework** | 159-test suite: 147 unit tests (pytest, in-memory SQLite) + 12 PostgreSQL integration tests covering the full SP execution lifecycle. 23 Selenium UI tests. In-app test runner at `/tests/` lets admins trigger the full suite and view per-test results without leaving the browser |
| **SP Run Detail** | Tracks every stored procedure invocation from a batch step. Shows status (`COMPLETED` / `FAILED`), timing, resolved parameters, and error messages. Accessible via the Run ID link on the batch execution detail page |

## Architecture

```
Dimensions (Org Unit, Product, Customer, Account, Transaction Number)
        ↓ validation
Staging (STG_INST_DATA, STG_GL_DATA, REF_INTEREST_RATE)
        ↓ Maker/Checker approval
        ↓ Post-Approval Actions (run_rules → Allocation Engine | stored_procedure → SP placeholder)
Processing (PROC_INST_DATA, PROC_GL_DATA)
        ↓ Allocation Engine (Pandas join + ratio shredding)
        ↓ per-dimension source filter  →  join  →  DEBIT dim mapping (output_dim_json)
                                                   CREDIT dim mapping (credit_dim_json)
Result  FCT_MGMT_INSTRUMENT  (entry_mode: BOTH | DEBIT_ONLY | CREDIT_ONLY, instrument-level)
        FCT_MGMT_LEDGER      (ledger output)

FTP Engine (Component-Based)
        REF_INTEREST_RATE (approved) → Independent Rule per Component (COF, LP, CLP, BUF)
        Result: Multiplexed pricing stored in PROC_INST_DATA (cost_of_fund, lp_amount, clp_amount, etc.)

## Architectural Governance

To maintain a **clean and sophisticated** codebase, BankPFT adheres to several advanced development principles:

1. **Service Layer Sovereignty**: All business logic must be encapsulated in `app/services/`. Routes (Blueprints) are strictly for HTTP orchestration, while Stored Procedures are strictly for high-performance set-based calculation. The Service layer bridges them by performing pre-calculation validation and audit logging.
2. **The Validation Gateway**: No engine (FTP, Allocation, Import) should execute without a prior validation pass. This ensures data integrity and as-of-date consistency before any records are mutated.
3. **Reproducibility Metadata**: Every execution stores a 'snapshot' of the active configuration in a `metadata_json` field. This allows users to trace results back to the exact rule state at the time of the run, even if the rule has since been edited.
4. **Structured Error Handling**: Generic exceptions are avoided. Each module throws domain-specific errors (e.g., `AllocationEngineError`) that carry context, allowing the UI to render graceful, actionable recovery steps.
```

Allocation ratios are stored in `REF_STATIC_ALLOCATION` and linked by `customer_id`. Each customer's ratios must sum to 1.0 per allocation group. Org reclassifications are stored in `REF_ORG_RECLASS` as 1:1 org-to-org mappings (ratio always 1.0).

## Tech Stack

- **Backend:** Flask 3.0, SQLAlchemy 2.0, Pandas 2.1, Flask-Login 0.6
- **Database:** PostgreSQL 16 (Docker) for development and production; SQLite (in-memory) for unit tests
- **PostgreSQL Driver:** psycopg2-binary 2.9.9
- **Frontend:** Bootstrap 5.3 (CDN), Bootstrap Icons
- **Auth:** Flask-Login with group-based role permissions
- **Upload:** openpyxl for Excel parsing
- **Deployment:** Gunicorn, Docker

## Quick Start

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | `dev-secret-change-in-production` | Flask session signing key — **set this in production** |
| `DATABASE_URL` | `postgresql://bankpft:bankpft_dev@localhost:5432/bankpft` | SQLAlchemy connection string. Falls back to `sqlite:///instance/bankpft.db` when unset |
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

This starts two services: **db** (PostgreSQL 16) and **web** (Flask/Gunicorn). The `DATABASE_URL` environment variable is set automatically via `docker-compose.yml`. Wait for the `db` service to report healthy before the web service accepts connections.

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
├── core/
│   ├── config_loader.py     # load_config(name) — centralised JSON config access
│   ├── filter_engine.py     # apply_df_filters() and apply_row_filters() — shared filter logic
│   ├── time_utils.py        # utc_now() — timezone-aware UTC helper used by all models & services
│   └── batch_logger.py      # BatchLogger class with standard logging methods (info, warning, error)
├── models/
│   ├── mixins.py            # TimestampMixin, MakerCheckerMixin — reusable SQLAlchemy column mixins
│   ├── auth.py              # User, Group, UserGroup (login & role management)
│   ├── dimensions.py        # DimOrgUnit, DimProduct, DimCustomer, DimAccount
│   ├── staging.py           # StgInstData, ProcInstData, StgGlData, ProcGlData
│   ├── allocation.py        # RefStaticAllocation, RefOrgReclass, RefStaticDistribution, RefStaticAlloc, FctMgmtLedger, FctMgmtInstrument
│   ├── ftp.py               # RefInterestRate, FtpProductConfig, FtpRun
│   ├── datafile.py          # DataFileBatch (import/export run history)
│   └── workflow.py          # UploadBatch, AllocationRule, BatchRun, BatchDefinition, BatchTask, BatchExecution, BatchExecutionStep
├── routes/
│   ├── auth.py              # Login, logout, change password
│   ├── admin.py             # User & group management (admin only)
│   ├── dashboard.py         # Home dashboard
│   ├── upload.py            # Data upload with Maker/Checker
│   ├── rules.py             # Allocation rule CRUD + JSON import
│   ├── batch.py             # Batch definitions, execution, and individual Allocation + FTP runs
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
│   ├── batch_executor.py    # Multi-task batch orchestrator (sequential step dispatch)
│   ├── sp_runner.py         # Synchronous stored-procedure executor (run_sp + SpRun tracking)
│   ├── test_runner.py       # In-app pytest runner — executes tests/, parses JSON report
│   └── testdata_service.py  # Test data generators (incl. FTP rate seeding)
└── templates/               # Jinja2 / Bootstrap 5 templates

db/
├── ddl/
│   ├── 00_all.sql                   # Monolithic concatenation of all schemas
│   ├── 01_auth.sql                  # Users & Groups
│   ├── 02_dimensions.sql            # Core dimensions (org, account, instrument lookup)
│   ├── 03_staging.sql               # Staging tables (GL, Instrument) with JSONB and processing status
│   ├── 04_reference.sql             # Allocation lookups and static mapping
│   ├── 05_fact.sql                  # Ledger and Instrument fact execution tables
│   ├── 06_ftp.sql                   # Funds Transfer Pricing configs and logs
│   ├── 07_workflow.sql              # Batch and Rule execution mappings capturing app state
│   ├── migration_sp_registry.sql    # Dynamic procedure registry table (`sys_registered_sp`)
│   ├── sp_alloc_log_table.sql       # Procedural debug execution trace core (`sys_sp_alloc_log`)
│   └── sp_call_log.sql              # Pytest integration audit definition
└── procedures/
    ├── sp_run_allocation.sql        # The Master Allocation Engine computational procedure
    ├── sp_month_end_sample.sql      # Template constraint for user batch execution deployments
    └── sp_test_echo.sql             # Isolated logic hook utilized exclusively by Pytest

development_prompt/
├── 1_frist_prompt.md        # AI rules, app factory init, and start.sh/bat bootstrapper
├── 1.5_prompt.md            # Generic helpers (time tracking & execution loggers)
├── 2_secnond_p.md           # Base layout, Bootstrap 5 UI shell, Authentication config
├── 3_prompt.md              # SQLAlchemy Model blueprints and MakerChecker Mixin config
├── 4_prompt.md              # PostgreSQL physical DDL mappings
├── 5_prompt.md              # JSON rules & definitions setup
├── 6_prompt.md              # Core business SP and Upload logic engines
├── 7_prompt.md              # Blueprint routing and WTForms wrappers
├── 8_prompt.md              # Jinja2 presentation templates and DataTables
├── 8.5_prompt.md            # Operational Dashboards & Batch Logging matrix
├── 9_prompt.md              # Pytest fixture & test suite generation
├── 10_prompt.md             # Mock user dataset generation service
└── 11_prompt.md             # Production Docker & Gunicorn deployment setup

tests/
├── __init__.py              # Package marker
├── conftest.py              # Shared fixtures (app, db_session, client, auth_client, seeded_db)
├── test_auth.py             # Auth, login/logout, access control, User/Group model
├── test_rules.py            # AllocationRule CRUD, JSON import, filter engine, allocation E2E
├── test_ftp_batch.py        # FTP config model, UI routes, lookback math, FTP engine, batch, datafile
├── test_api.py              # All /api/v1/ endpoints (auth guard, happy path, validation)
├── test_sp_batch.py         # SpRun model, sp_runner service, batch executor CUSTOM_SP, SP monitor routes (26 tests)
└── test_sp_integration.py   # PostgreSQL live integration: sp_test_echo DDL, dispatch_sp end-to-end (12 tests)
```

### UI Navigation Structure
The platform is heavily structured around a centralized sidebar matrix defined in `base.html`. All functional screens must seamlessly nest within one of these specific navigation hierarchies:

- **Dashboard**
- **Data Management**
  - Manual Data Load
  - Data Files
- **Allocation Rules**
- **Fund Transfer Pricing**
- **Batch**
  - Monitor
  - Execution
  - Definitions
  - Registered SPs
- **Reports**
- **Test Data**
- **Admin Tools** (requires `is_admin` flag)
  - Users / Groups
  - JSON Configurations
  - Test Suite

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
| User's chosen rule config | **DB** `allocation_rule` | `source_table`, `lookup_table`, `output_table`, `join_key`, `allocation_method` saved per rule |
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
1. Route executes `BatchExecutor` which invokes the `ALLOCATION` abstraction.
2. The `app.services.allocation_engine` parses `rule_config.json` and loads the selected rule context (Filter logic and Dimension mappings).
3. The Python engine formats those properties into a deterministic JSON object mapping.
4. Python securely dispatches execution natively to PostgreSQL via `sp_run_allocation(rule_id, as_of_date, 'BOTH', json_payload)`.

── Inside PostgreSQL Stored Procedure ──
5. Dynamic SQL generates queries applying JSON filters physically on the database layer (`proc_inst_data` or `proc_gl_data`).
6. Based on method (`RATIO`, `DISTRIBUTION`, or `STATIC`), the procedure executes native `INNER JOIN` operations against `ref_static_distribution` or `ref_static_allocation`.
7. Source balances are mathematically generated inside the temp table (balance × ratio). Output dimensions map directly from the matched target lookup.
8. The procedure maps explicit DEBIT and CREDIT columns dynamically based on `output_dim_json` mapping. Orhpans are defaulted securely to 1.0 ratio.

── Idempotent Write Lifecycle ──
9. The Transaction structurally enforces `DELETE FROM fct_mgmt_instrument WHERE allocation_id = rule_id AND as_of_date = run_date` resolving duplications.
10. The procedure commits the generated allocation allocations securely mapping traces into `sys_sp_alloc_log`. Python receives success validation, avoiding heavy multi-gigabyte pandas merges entirely.
```

**Traceability:** Every output row stores the generating rule's `allocation_id` (= `AllocationRule.id`). This allows downstream reports and audits to trace any `fct_mgmt_*` record back to the rule that produced it.

**Idempotent re-runs:** Re-running the same rule for the same as-of date replaces (deletes then inserts) the previous output. This guarantees no duplicate records and ensures the output always reflects the latest rule configuration.

**To add a new source table:** add its column config to `allocation_config.json` and its option to `rule_config.json`.

### Multi-Task Batch Definitions

The batch system allows grouping multiple engine calls into a single, ordered execution sequence.

| Aspect | Source | Details |
|---|---|---|
| Batch definition name, description, continue-on-error | **DB** `batch_definition` | Created by admin in the Batch Definitions UI |
| Step order, task type, ref ID, label | **DB** `batch_task` | Each step references a rule ID, format name, or SP name |
| Execution record (start/end, status, as-of date) | **DB** `batch_execution` | UUID primary key; created by `batch_executor.run_batch()` |
| Per-step result (status, summary, error, ref_run_id) | **DB** `batch_execution_step` | One row per step; `ref_run_id` links to underlying engine run |

**Supported task types:**

| Type | Engine called | `ref_id` meaning |
|---|---|---|
| `ALLOCATION` | `allocation_engine.run_allocation(ref_id, as_of, user)` | `allocation_rule.id` |
| `FTP` | `ftp_engine.run_ftp(as_of, user)` | *(none — runs all active FTP configs)* |
| `DATAFILE_IMPORT` | `datafile_service.import_file(path, format_name)` | Format name from `upload_config.json` |
| `DATAFILE_EXPORT` | `datafile_service.export_data(format_name, user, date)` | Format name |
| `CUSTOM_SP` | `sp_runner.run_sp(sp_name, params, run_by, exec_step_id)` | Stored procedure name (optional `schema.` prefix). Executes synchronously; step becomes `COMPLETED` or `FAILED` like any other step |

**Orchestrator flow** (`app/services/batch_executor.py`):
```
1. Load BatchDefinition + ordered BatchTask list
2. Create BatchExecution record (RUNNING)
3. Pre-create all BatchExecutionStep records (PENDING)
4. For each step in order:
   a. Mark step RUNNING
   b. Dispatch to correct engine based on task_type
   c. On success: mark COMPLETED, store ref_run_id + summary
   d. On failure: mark FAILED, store error_message
      - if continue_on_error=False → mark remaining steps SKIPPED, stop
5. Mark BatchExecution COMPLETED / FAILED / PARTIAL
```

**CUSTOM_SP runtime token resolution:**

| Token | Resolved value | Example |
|---|---|---|
| `{as_of_date}` | Batch as-of-date (ISO string) | `"2026-04-30"` |
| `{run_by}` | Username who triggered the batch | `"admin"` |

Tokens are substituted in the `params` JSON values before the SP is called.

### Stored Procedure Registry

System administrators can register stored procedures for use within Batch Definitions. Accessible via `/batch/procedures`, the registry dynamically scans the `information_schema.routines` table to auto-discover all available database procedures. Admins can selectively toggle which procedures are "Batch Enabled."

When configuring a Multi-Task Batch Definition, any step defined as `CUSTOM_SP` will enforce a dropdown selection restricted exclusively to these enabled, registered procedures, guaranteeing schema integrity and preventing typos.

## Lookup Tables

The system supports multiple lookup tables that the allocation engine can join against:

| Lookup Table | Method | Purpose | Join Key | Ratio |
|---|---|---|---|---|
| `ref_static_allocation` | RATIO | Shred balances across orgs by customer-level ratios | `customer_id` | Variable (must sum to 1.0 per group) |
| `ref_org_reclass` | RATIO | Reclassify one org unit to another (1:1 mapping) | `org_unit_id` | Always 1.0 |
| `ref_static_distribution` | DISTRIBUTION | Flexible ratio shredding; output dimension taken from `target_dim` column. Supports multiple named **driver sets** within one table — each row carries a `driver_name`; a rule references one driver by name via `distribution_driver` | `customer_id` / `org_unit_id` / `product_code` | Variable (must sum to 1.0 per `driver_name` + `distribution_id` group) |
| (None) | STATIC | 1:1 source-to-target mapping. Does not perform a lookup join; uses dimensions from source or fixed values. | (n/a) | Configurable per rule via **Fixed Ratio** (defaults to 1.0) |

## Fund Transfer Pricing (FTP)

The FTP engine is decoupled into a granular **Component Architecture**. It operates on `proc_inst_data` directly, calculating multiple pricing components in a single pass.

### Component Types
- **COF (Cost of Funds):** The base funding rate.
- **LP (Liquidity Premium):** Add-on for liquidity risk.
- **CLP (Contingent Liquidity Premium):** Add-on for contingent risk.
- **BUF (Buffer Asset Cost):** Cost of maintaining liquid assets.

### Data Model

| Table | Purpose |
|---|---|
| `ref_interest_rate` | Uploaded rate curves (Maker/Checker approved). |
| `ftp_model_rule` | Component-specific rules defining method, rate code, and tenor for a specific component (COF/LP/CLP/BUF). |
| `ftp_model` | Groups multiple rules (one for each component) into a logical pricing model. |
| `ftp_process` | Binds an FTP Model to a target population (filter-based) for batch execution. |
| `ftp_run` | Execution log: status, duration, and processed counts. |

### Calculation Method: MOVING_AVG

1. The engine retrieves all active rules for the instrument's product code.
2. For **each component** (COF, LP, CLP, BUF):
   a. Look up the assigned Rule (Rate Code, Tenor, Avg Period).
   b. Compute `base_rate` = moving average for that curve over the lookback window.
   c. Calculate component amount = `balance × base_rate × (days_in_month / days_in_year)`.
3. Results are written back to native columns in `proc_inst_data` (e.g., `lp_rate`, `lp_amount`).

### FTP Configuration
Managed through the **FTP Rules** and **FTP Models** UI, allowing for flexible matrix-based pricing without code changes.

### FTP Import
Supports importing complex model/rule hierarchies via JSON or via the REST API.

## JSON Configuration Files

### `app/config/upload_config.json`

Defines each upload data type (INSTRUMENT, GL, ALLOCATION, ORG_RECLASS, DISTRIBUTION, STATIC_ALLOC) with:
- **label / description** — display name and tooltip shown in the upload form
- **required_columns / optional_columns** — which columns must exist in the upload
- **unique_key** — column checked for duplicates (e.g. `account_id`)
- **dimension_lookups** — maps upload columns to dimension tables for referential integrity checks
- **column_mapping** — type casting rules (date/float/string) with defaults for optional fields
- **numeric_ranges** — per-column min/max bounds (e.g. `ratio: {min: 0, max: 1}`)
- **ratio_validation** — group-by keys, expected sum, and tolerance for allocation ratio checks
- **validation_rules** — ordered list of rule IDs to run for this data type (references `validation_rules.json`)
- **post_approval** — action to trigger automatically when the batch is approved:
  - `{"type": "run_rules", "rule_ids": [4, 5]}` — runs the listed `AllocationRule` IDs using `date.today()`
  - `{"type": "stored_procedure", "procedure_name": "sp_name"}` — POC placeholder; replace body to call a real SP
  - `null` — no post-approval action

The upload form dropdown and expected-columns display are rendered dynamically from this file.

> **DISTRIBUTION type:** The `driver_name` column is required (alongside `distribution_id`, `target_dim`, `ratio`). The `ratio_validation` group-by is `[driver_name, distribution_id]` so ratios sum to 1.0 within each driver/distribution-id combination.

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
- **lookup_tables** — selectable lookup tables (e.g. Static Allocation, Org Reclassification, Static Distribution, Static Alloc)
- **output_tables** — selectable output tables
- **join_keys** — selectable join keys (e.g. `customer_id`, `org_unit_id`, `product_code`)
- **allocation_methods** — the three method options shown as radio buttons: `RATIO`, `DISTRIBUTION`, `STATIC`
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
- **lookup_tables** — keyed by table name, each with `columns`, `ratio_column`, `id_column`, `target_org_column`, `status_filter`; `ref_static_distribution` also carries `driver_filter_column: "driver_name"` which the engine uses to filter rows by the active driver
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
3. **Upload data** — Go to **Data Management → Manual Data Load** (or `/upload/new`), select data type, upload the Excel file. Validation runs automatically
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

### Interactive Error Grids

When data validations fail during a manual file upload, the UI natively renders a Bootstrap Error Grid detailing the exact row number, column name, and specific error message preventing submission. If the file passes seamlessly, a "Data Integrity Check: PASSED" banner validates the success.

## Output Tables

| Table | Purpose |
|---|---|
| `fct_mgmt_instrument` | Instrument-level allocation output — DEBIT + CREDIT offset entries (recommended default) |
| `fct_mgmt_ledger` | Legacy ledger output — retains backward compatibility |

Both tables share the same schema, with `entry_type` column indicating `DEBIT` or `CREDIT`.

**Key columns:**

| Column | Description |
|---|---|
| `allocation_id` | The ID of the `AllocationRule` that generated this row — enables traceability from output back to rule |
| `as_of_date` | The calculation date passed at batch execution time |
| `entry_type` | `DEBIT` or `CREDIT` |
| `financial_element` | Balance column label when financial-element unpivot is active (e.g. `BAL`, `NII`) |
| `batch_run_id` | UUID of the `BatchRun` record for this execution |

Re-running a rule for the same `as_of_date` deletes all prior output rows with that `allocation_id` + `as_of_date` combination before inserting new rows, ensuring idempotent results.

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
  "allocation_method": "RATIO",
  "distribution_driver": null,
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

## FTP Product Config JSON Import

FTP product configurations can be imported in bulk from a JSON file via `/ftp/config/import` (UI) or `POST /api/v1/ftp/config/import` (REST API). If a `product_code` already exists, its configuration is updated in-place.

**Single config object:**
```json
{
  "product_code": "LOAN_FIXED",
  "rate_code": "SWAP_RATE",
  "term": 5,
  "term_mult": "Y",
  "avg_period": 3,
  "avg_period_mult": "M",
  "is_active": true
}
```

**Array of config objects:**
```json
[
  { "product_code": "LOAN_FIXED", "rate_code": "SWAP_RATE", "term": 5, "term_mult": "Y", "avg_period": 3, "avg_period_mult": "M" },
  { "product_code": "DEPOSIT",    "rate_code": "LIBOR_USD",  "term": 3, "term_mult": "M", "avg_period": 1, "avg_period_mult": "M" }
]
```

| Field | Required | Default | Notes |
|---|---|---|---|
| `product_code` | Yes | — | Must be unique; matches `dim_product` |
| `rate_code` | Yes | — | Matches `interest_rate_code` in rate table |
| `term` | Yes | — | Positive integer tenor number |
| `term_mult` | No | `M` | `D` / `M` / `Y` |
| `avg_period` | No | `1` | Moving-average lookback period length |
| `avg_period_mult` | No | `M` | `D` / `M` / `Y` |
| `method` | No | `MOVING_AVG` | Only supported method |
| `is_active` | No | `true` | Whether config is used by the FTP engine |

A reference file with five sample configs is at `sample_ftp_config.json` in the project root.

## Data File Management

Accessible from **Data Management → Data Files** in the sidebar (`/datafile`).

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
| `POST` | `/api/v1/rules/import` | Import an allocation rule from JSON body |
| `POST` | `/api/v1/batch/allocation` | Run an allocation batch |
| `GET` | `/api/v1/batch/allocation/<id>` | Get allocation batch status |
| `POST` | `/api/v1/batch/ftp` | Run the FTP calculation engine |
| `GET` | `/api/v1/batch/ftp/<id>` | Get FTP run status |
| `GET` | `/api/v1/ftp/configs` | List all FTP product configurations |
| `POST` | `/api/v1/ftp/config/import` | Import one or more FTP product configs from JSON |

**POST `/api/v1/batch/allocation`**
```json
{ "rule_id": 1, "as_of_date": "2026-01-01" }
```

**POST `/api/v1/batch/ftp`**
```json
{ "as_of_date": "2026-01-01" }
```

**POST `/api/v1/rules/import`** — import an allocation rule directly from JSON:
```json
{
  "name": "Customer Shred Q1",
  "source_table": "proc_inst_data",
  "lookup_table": "ref_static_allocation",
  "output_table": "fct_mgmt_instrument",
  "join_key": "customer_id",
  "allocation_method": "RATIO",
  "entry_mode": "BOTH",
  "filter_json": {"logic": "AND", "conditions": [{"field": "product_code", "operator": "in", "value": "LOAN,DEPOSIT"}]},
  "output_dim_json": {"org_unit_id": {"mode": "lookup", "lookup_column": "target_org_unit_id"}}
}
```

Response (201 Created):
```json
{ "rule_id": 5, "name": "Customer Shred Q1", "status": "ACTIVE", "entry_mode": "BOTH", "created_by": "admin", "created_at": "2026-04-04T00:00:00Z" }
```

**POST `/api/v1/ftp/config/import`** — import one or more FTP product configs:
```json
[
  { "product_code": "LOAN_FIXED", "rate_code": "SWAP_RATE", "term": 5, "term_mult": "Y", "avg_period": 3, "avg_period_mult": "M" },
  { "product_code": "DEPOSIT",    "rate_code": "LIBOR_USD",  "term": 3, "term_mult": "M" }
]
```

Response:
```json
{ "imported": 2, "updated": 0, "skipped": 0, "errors": [] }
```

**GET `/api/v1/ftp/configs`**:
```json
{
  "configs": [
    { "id": 1, "product_code": "LOAN_FIXED", "method": "MOVING_AVG", "rate_code": "SWAP_RATE",
      "term": 5, "term_mult": "Y", "avg_period": 3, "avg_period_mult": "M", "is_active": true, "created_by": "admin" }
  ]
}
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

### Multi-Task Batch Definition & Execution Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/batch/definitions` | List active batch definitions |
| `GET` | `/api/v1/batch/definitions/<id>` | Get definition with ordered step list |
| `POST` | `/api/v1/batch/definitions/<id>/run` | Execute a batch definition |
| `GET` | `/api/v1/batch/executions/<exec_id>` | Poll execution status and per-step results |

**GET `/api/v1/batch/definitions`**
```json
{
  "definitions": [
    {
      "definition_id": 1,
      "name": "Month-End Close",
      "description": "Full month-end allocation and FTP run",
      "continue_on_error": false,
      "is_active": true,
      "step_count": 4,
      "created_by": "admin",
      "created_at": "2026-01-01T00:00:00Z"
    }
  ]
}
```

**GET `/api/v1/batch/definitions/1`** — includes `steps` array:
```json
{
  "definition_id": 1,
  "name": "Month-End Close",
  "continue_on_error": false,
  "step_count": 4,
  "steps": [
    { "step_order": 1, "task_type": "DATAFILE_IMPORT", "ref_id": "LOAN_FIXED",         "label": "Import loan file" },
    { "step_order": 2, "task_type": "ALLOCATION",      "ref_id": "1",                  "label": "Shred inst balances" },
    { "step_order": 3, "task_type": "FTP",             "ref_id": null,                 "label": "FTP calculation" },
    { "step_order": 4, "task_type": "DATAFILE_EXPORT", "ref_id": "ALLOC_RESULT_EXPORT", "label": "Export results" }
  ]
}
```

**POST `/api/v1/batch/definitions/1/run`**
```json
{ "as_of_date": "2026-01-31" }
```

**Response (execution with per-step results):**
```json
{
  "execution_id": "a3f9b1c2-...",
  "definition_id": 1,
  "definition_name": "Month-End Close",
  "as_of_date": "2026-01-31",
  "status": "COMPLETED",
  "run_by": "admin",
  "error_message": null,
  "started_at": "2026-01-31T00:00:00Z",
  "completed_at": "2026-01-31T00:01:12Z",
  "steps": [
    {
      "step_order": 1,
      "task_type": "DATAFILE_IMPORT",
      "label": "Import loan file",
      "status": "COMPLETED",
      "ref_run_id": "b4c2...",
      "summary": "1200 rows imported",
      "error_message": null,
      "started_at": "2026-01-31T00:00:00Z",
      "completed_at": "2026-01-31T00:00:05Z"
    },
    {
      "step_order": 2,
      "task_type": "ALLOCATION",
      "label": "Shred inst balances",
      "status": "COMPLETED",
      "ref_run_id": "c5d3...",
      "summary": "src=1200 out=2400 variance=0.0",
      "error_message": null,
      "started_at": "2026-01-31T00:00:05Z",
      "completed_at": "2026-01-31T00:00:22Z"
    },
    {
      "step_order": 3,
      "task_type": "FTP",
      "label": "FTP calculation",
      "status": "COMPLETED",
      "ref_run_id": "d6e4...",
      "summary": "processed=1200 matched=1150",
      "error_message": null,
      "started_at": "2026-01-31T00:00:22Z",
      "completed_at": "2026-01-31T00:01:04Z"
    },
    {
      "step_order": 4,
      "task_type": "DATAFILE_EXPORT",
      "label": "Export results",
      "status": "COMPLETED",
      "ref_run_id": "e7f5...",
      "summary": "2400 rows exported",
      "error_message": null,
      "started_at": "2026-01-31T00:01:04Z",
      "completed_at": "2026-01-31T00:01:12Z"
    }
  ]
}
```

**Execution status values:**

| Status | Meaning |
|---|---|
| `RUNNING` | Execution is in progress |
| `COMPLETED` | All steps completed successfully |
| `FAILED` | First step failed and `continue_on_error=false` |
| `PARTIAL` | One or more steps failed but `continue_on_error=true` allowed remaining steps to run |

**Step status values:** `PENDING` → `RUNNING` → `COMPLETED` / `FAILED` / `SKIPPED`

**curl examples:**
```bash
BASE=http://localhost:5000
AUTH="-u admin:admin"

# List active batch definitions
curl $AUTH $BASE/api/v1/batch/definitions

# Get definition 1 with step list
curl $AUTH $BASE/api/v1/batch/definitions/1

# Execute definition 1 for 2026-01-31
curl $AUTH -X POST -H 'Content-Type: application/json' \\
  -d '{"as_of_date":"2026-01-31"}' \\
  $BASE/api/v1/batch/definitions/1/run

# Poll execution status
curl $AUTH $BASE/api/v1/batch/executions/<execution_id>
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

## Test Framework

BankPFT ships with a fully integrated regression test suite and an in-app test runner. The framework ensures that inter-dependent enterprise workflows — allocation engine, FTP engine, Maker/Checker workflow, REST API — remain correct as the codebase grows.

### Quick Run (command line)

```bash
# Activate virtualenv if not active
source venv/bin/activate

# Run the full suite
python -m pytest tests/ -q

# Run a single module
python -m pytest tests/test_api.py -v

# Run a single test
python -m pytest tests/test_rules.py::TestAllocationEngine::test_run_allocation_creates_batch -v
```

**Current result: 151 passed, 0 failed** — unit tests use in-memory SQLite, ~17 seconds.

To run only unit tests (no browser required):
```bash
python -m pytest tests/ --ignore=tests/test_ui.py -q
```

To run only UI tests:
```bash
python -m pytest tests/test_ui.py -v
```

To run PostgreSQL integration tests (requires a live PostgreSQL instance):
```bash
DATABASE_URL="postgresql://bankpft:bankpft_dev@localhost:5432/bankpft" \
  python -m pytest tests/test_sp_integration.py -v -m integration
```

### In-App Test Runner

Admins can trigger the test suite and view results directly from the browser without using the terminal:

| URL | Description |
|---|---|
| `/tests/` | Run history — all past runs with pass/fail summary badges |
| **Run Full Suite** button | Triggers `pytest tests/` as a subprocess; redirects to results when done |
| `/tests/run/<id>` | Per-test results grouped by module — outcome, duration, error message |
| `/tests/run/<id>/log` | Raw pytest stdout (plain text) |

The "Test Suite" link appears in the sidebar under the Admin section for Admin users.

### Test Suite Overview

| File | Tests | What is tested |
|---|---|---|
| `tests/test_auth.py` | 18 | Login, logout, wrong credentials, protected route redirects, User model password hashing, group permissions, admin property, admin routes (users + groups list) |
| `tests/test_rules.py` | 26 | AllocationRule model defaults, UI routes, JSON import (valid/missing name), `_apply_filters()` for eq / gt / in / OR / between / invalid JSON, allocation engine end-to-end, DEBIT+CREDIT balance equality, Static Allocation engine (no-orphan guarantee), Distribution driver filtering and storage, `RefStaticDistribution` and `RefStaticAlloc` model constraints |
| `tests/test_ftp_batch.py` | 25 | FtpProductConfig model, unique constraint, FTP UI routes, import single/array JSON, `_lookback_start()` for D/M/Y across year boundaries, FTP engine E2E match & rate write-back, zero-instrument clean run, BatchDefinition model, datafile config loading and format validation |
| `tests/test_api.py` | 33 | 401 guard on every endpoint, wrong credentials, GET listing shapes, `POST /api/v1/rules/import` (valid, missing name, empty body), `POST /api/v1/ftp/config/import` (single, array, update, missing product_code), datafile path-traversal rejection, allocation missing rule_id, FTP run with and without date |
| `tests/test_sp_batch.py` | 22 | SpRun model, sp_runner param resolution and SP-name validation, batch executor CUSTOM_SP synchronous execution, SP run detail and status endpoint routes |
| `tests/test_ui.py` | 23 | Selenium headless-Chrome browser tests — login flow, sidebar navigation, filter editor (empty state, add/remove condition rows, AND/OR radios), file upload input fields on rule import and FTP import pages, admin user/group pages |
| **Unit total** | **147** | |
| `tests/test_sp_integration.py` | 12 | *PostgreSQL required* — sp_test_echo procedure in catalog, sp_call_log table, direct CALL writes audit row, NULL params, run_sp end-to-end (SpRun COMPLETED, audit row written, `{as_of_date}` token resolved), invalid SP name raises ValueError, non-existent SP → FAILED status |
| **Grand total** | **159** | |

### Test Isolation

- Each test runs against an **in-memory SQLite database** (`sqlite:///:memory:`) — the production `instance/bankpft.db` is never touched.
- Each test function is wrapped in a transaction that is **rolled back** when the test completes, so tests are fully independent.
- The `seeded_db` fixture inserts minimal master data (dimensions, one instrument row, allocation ratio, FTP config, interest rate) for engine-level tests.
- The `auth_client` fixture logs in as `admin` via the form POST so UI route tests have an authenticated session.

### Adding Tests for New Features

1. Create `tests/test_<feature>.py` — it is auto-discovered by pytest.
2. Use `client` for unauthenticated routes, `auth_client` for admin UI, `seeded_db` when the engine needs data.
3. Follow the class-per-concern pattern (`TestMyModelRoutes`, `TestMyEngine`).
4. Run `python -m pytest tests/ -q` or click **Run Full Suite** in the app to validate.

### Dependencies

```
pytest>=8.0
pytest-json-report>=1.5.0
selenium>=4.0
webdriver-manager>=4.0
```

All are listed in `requirements.txt` and installed by `./start.sh` or `pip install -r requirements.txt`.

The `pytest.ini` at the project root registers the `ui` and `integration` custom marks so pytest does not emit warnings when running those tests. The marks allow selectively running or skipping tests:

```bash
# Run only tests NOT requiring a browser or PostgreSQL
python -m pytest tests/ -m "not ui and not integration" -q

# Run only browser tests
python -m pytest tests/ -m ui -v

# Run only PostgreSQL integration tests
python -m pytest tests/ -m integration -v
```

For a detailed reference — fixture descriptions, test case catalogue, how to extend the suite, and in-app runner internals — see [docs/TEST_FRAMEWORK.md](docs/TEST_FRAMEWORK.md).

---

## start.sh Reference

| Command | Description |
|---|---|
| `./start.sh` or `./start.sh dev` | Flask development server with auto-reload |
| `./start.sh prod` | Gunicorn daemon (4 workers, logs to `bankpft.log`) |
| `./start.sh stop` | Stop a running Gunicorn daemon |
| `./start.sh docker` | Build and start via Docker Compose |

Environment variable: `WORKERS=8 ./start.sh prod` overrides the default 4 Gunicorn workers.



## Authentication Implementation Consideration

This prototype uses HTTP Basic Auth for simplicity. For a production deployment of an internal EPM/allocation engine, Microsoft **Azure AD (Entra ID)** is the recommended identity provider. Two distinct OAuth 2.0 flows cover the two principal actors in the system.

---

### Flow 1 — OIDC / Authorization Code Flow (Interactive Users)

Used by **human users** accessing the web UI or calling the API from a personal client (e.g. Postman, a script run under a personal identity).

```
Browser / Client
      │
      │  1. Redirect to Entra ID login
      │     GET https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize
      │        ?client_id={app_client_id}
      │        &response_type=code
      │        &redirect_uri=https://bankpft.internal/auth/callback
      │        &scope=openid profile email
      │        &state={csrf_token}
      │
      │  2. User authenticates (MFA, SSPI, etc.)
      │
      │  3. Entra ID redirects back with auth code
      │     GET https://bankpft.internal/auth/callback?code=...&state=...
      │
      │  4. Flask exchanges code for tokens
POST https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token
      body: grant_type=authorization_code
            code={auth_code}
            redirect_uri=https://bankpft.internal/auth/callback
            client_id={app_client_id}
            client_secret={app_client_secret}
      │
      │  5. Entra ID returns id_token + access_token + refresh_token
      │
      │  6. Flask validates id_token (JWT), extracts UPN/groups, creates session
```

**Flask integration — recommended libraries:**

| Library | Role |
|---|---|
| `msal` (Microsoft MSAL for Python) | Token acquisition, cache, refresh |
| `flask-session` | Server-side session (Redis / DB backed) |
| `PyJWT` + `cryptography` | Local `id_token` validation (RS256) |

**Key points for the allocation engine:**
- Map Entra ID **group claims** (`groups` in the JWT) → BankPFT user groups at first login (provision on the fly).
- Store the MSAL token cache server-side (not in a cookie) — use `msal.SerializableTokenCache` backed by Redis or SQLite.
- Set `SESSION_COOKIE_HTTPONLY=True`, `SESSION_COOKIE_SECURE=True`, `SESSION_COOKIE_SAMESITE="Lax"` in Flask config.
- Validate `iss`, `aud`, `exp`, and `nonce` claims on every `id_token`.

---

### Flow 2 — Client Credentials Flow (App-to-App / A2A)

Used by **automated systems** — schedulers, ETL pipelines, upstream GL systems — that call the REST API without a human present.

```
Calling Service (e.g. GL batch job)
      │
      │  1. Acquire token directly from Entra ID (no user redirect)
POST https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token
      body: grant_type=client_credentials
            client_id={caller_app_client_id}
            client_secret={caller_app_client_secret}   # or certificate
            scope=api://{bankpft_app_client_id}/.default
      │
      │  2. Entra ID returns access_token (JWT, no refresh token)
      │
      │  3. Caller attaches token to every API request
      GET /api/v1/datafile/formats
      Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGci...
      │
      │  4. Flask validates token
      │     - Fetch JWKS from https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys
      │     - Verify RS256 signature, iss, aud, exp
      │     - Extract appid / azp claim to identify the calling service
      │     - Map appid → BankPFT service account / role
```

**Flask middleware sketch:**

```python
# app/auth/entra.py
import jwt, requests
from functools import wraps
from flask import request, abort, g

ENTRA_JWKS_URL = "https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
EXPECTED_AUD   = "api://{bankpft_app_client_id}"
EXPECTED_ISS   = "https://login.microsoftonline.com/{tenant_id}/v2.0"

def _get_jwks():
    # Cache this in Redis / memory — refreshes when kid not found
    return requests.get(ENTRA_JWKS_URL).json()

def require_bearer(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            abort(401)
        token = auth.split(" ", 1)[1]
        try:
            header = jwt.get_unverified_header(token)
            key    = _find_key(_get_jwks(), header["kid"])
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=EXPECTED_AUD,
                issuer=EXPECTED_ISS,
            )
        except jwt.PyJWTError:
            abort(401)
        g.caller_app_id = claims.get("appid") or claims.get("azp")
        return f(*args, **kwargs)
    return decorated
```

**Key points:**

| Point | Detail |
|---|---|
| No user context | `sub` claim identifies the *application*, not a person — map `appid` to a named service account in BankPFT's user table |
| Use certificates in prod | `client_secret` rotates manually; an X.509 cert uploaded to Entra ID is more secure and supports automated rotation via Key Vault |
| Scope the permissions | Define **App Roles** on the BankPFT Entra app registration (e.g. `DataFile.Import`, `Allocation.Run`) and check `roles` claim inside `require_bearer` |
| JWKS cache | Cache the public keys and only re-fetch when a new `kid` appears — avoids a round-trip to Entra on every API call |

---

### Side-by-side comparison

| Dimension | Auth Code + OIDC | Client Credentials |
|---|---|---|
| Actor | Human user (browser / Postman) | Service / daemon / scheduler |
| Involves a redirect? | Yes (browser login page) | No |
| Token type returned | `id_token` + `access_token` + `refresh_token` | `access_token` only |
| Identity in token | User UPN, groups | Application ID, app roles |
| Session management | Flask server-side session | Stateless — validate JWT per request |
| Secret rotation | MSAL refresh token handles re-auth | Key Vault cert or scheduled secret rotation |
| Flask library | `msal` + `flask-session` | `PyJWT` + `cryptography` |

---

### Entra ID App Registration checklist

- **One app registration** for BankPFT itself (the resource / API server).
- **Separate app registrations** for each calling service (A2A clients).
- Enable **group claims** in the token manifest (`"groupMembershipClaims": "SecurityGroup"`).
- Define **App Roles** for coarse-grained API authorization (`DataFile.Import`, `Allocation.Run`, `Report.Read`).
- Set the **Redirect URI** (Auth Code flow only): `https://bankpft.internal/auth/callback`.
- Grant **admin consent** on the tenant for the `/.default` scope used by A2A callers.

---

## Batch Parallel Run & Async UI Implementation Consideration

The current engine runs each `BatchRun` synchronously inside the HTTP request. For month-end or large entity volumes this blocks the web worker for minutes and makes the UI unresponsive. Two complementary patterns solve this.

---

### Pattern 1 — Parallel rule execution (multi-threading / multi-processing)

Each `AllocationRule` is independent (separate source rows, separate output rows). They can be fanned out concurrently.

**Current flow (synchronous):**
```
POST /api/v1/batch/run
  └── for rule_id in rule_ids:
        engine.run_rule(rule_id, as_of_date)   # blocks until done
  └── return 200
```

**Target flow (parallel):**
```
POST /api/v1/batch/run
  └── executor = ThreadPoolExecutor(max_workers=N)
  └── futures = {executor.submit(engine.run_rule, rule_id, date): rule_id for rule_id in rule_ids}
  └── for future in as_completed(futures):
        result = future.result()               # collect per-rule outcome
  └── return 200 (all done) or 207 (partial failures)
```

**Implementation options:**

| Option | Library | Best for |
|---|---|---|
| Thread pool | `concurrent.futures.ThreadPoolExecutor` | I/O-bound rules (DB reads/writes) — simplest change |
| Process pool | `concurrent.futures.ProcessPoolExecutor` | CPU-bound transform logic |
| Celery + Redis | `celery`, `redis` | Production; per-rule retry, visibility, rate limiting |
| APScheduler | `apscheduler` | Scheduled month-end runs without Celery overhead |

**Thread pool sketch (minimal change to `allocation_engine.py`):**

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def run_batch_parallel(rule_ids: list[int], as_of_date: date, max_workers: int = 4):
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(run_rule, rid, as_of_date): rid for rid in rule_ids}
        for future in as_completed(futures):
            rid = futures[future]
            try:
                results[rid] = future.result()   # BatchRun record
            except Exception as exc:
                results[rid] = {"status": "FAILED", "error": str(exc)}
    return results
```

**Concurrency guard — avoid double-posting:**
```sql
-- Before inserting a BatchRun, check no RUNNING run exists for same rule + date
SELECT 1 FROM batch_run
WHERE rule_id = :rule_id AND as_of_date = :date AND status = 'RUNNING'
LIMIT 1;
```

---

### Pattern 2 — Async / fire-and-forget with real-time UI

For runs that take > ~5 seconds, the HTTP response should return immediately with a job ID, and the browser should poll (or stream) for progress — eliminating gateway timeouts and giving users a live status screen.

**Request/response contract:**

```
POST /api/v1/batch/run
Body: { "rule_ids": [1,2,3], "as_of_date": "2026-03-31" }

→ 202 Accepted
{
  "job_id": "a3f9...",
  "status_url": "/api/v1/batch/job/a3f9...",
  "message": "Batch queued. Poll status_url for updates."
}
```

**Backend (Celery task):**

```python
# app/tasks/batch_tasks.py
from celery import Celery, group
from app.services.allocation_engine import run_rule

celery_app = Celery("bankpft", broker="redis://localhost:6379/0",
                    backend="redis://localhost:6379/1")

@celery_app.task(bind=True)
def run_rule_task(self, rule_id: int, as_of_date: str):
    try:
        result = run_rule(rule_id, date.fromisoformat(as_of_date))
        return {"rule_id": rule_id, "batch_run_id": result.id, "status": "COMPLETED"}
    except Exception as exc:
        self.update_state(state="FAILURE", meta={"exc": str(exc)})
        raise

def submit_batch_job(rule_ids: list[int], as_of_date: str) -> str:
    job = group(run_rule_task.s(rid, as_of_date) for rid in rule_ids)
    result = job.apply_async()
    return result.id   # group result ID → stored in Redis
```

**Flask route (fire-and-forget):**

```python
@bp.post("/batch/run")
@require_bearer
def start_batch():
    body        = request.get_json()
    rule_ids    = body["rule_ids"]
    as_of_date  = body["as_of_date"]
    job_id      = submit_batch_job(rule_ids, as_of_date)
    return jsonify({"job_id": job_id,
                    "status_url": f"/api/v1/batch/job/{job_id}"}), 202

@bp.get("/batch/job/<job_id>")
@require_bearer
def poll_batch(job_id):
    result = celery_app.GroupResult.restore(job_id)
    if result is None:
        return jsonify({"error": "unknown job"}), 404
    completed = [r for r in result.results if r.ready()]
    return jsonify({
        "job_id":     job_id,
        "total":      len(result.results),
        "completed":  len(completed),
        "failed":     sum(1 for r in result.results if r.failed()),
        "done":       result.ready(),
        "results":    [r.result for r in completed],
    })
```

**Frontend — async status screen:**

```javascript
// Poll every 3 seconds until done; update a progress bar
async function runBatch(ruleIds, asOfDate) {
  const resp = await fetch("/api/v1/batch/run", {
    method: "POST",
    headers: { "Content-Type": "application/json", "Authorization": bearerHeader },
    body: JSON.stringify({ rule_ids: ruleIds, as_of_date: asOfDate })
  });
  const { job_id, status_url } = await resp.json(); // 202 Accepted

  const poll = setInterval(async () => {
    const status = await fetch(status_url, { headers: { "Authorization": bearerHeader } });
    const data   = await status.json();
    updateProgressBar(data.completed, data.total, data.failed);
    if (data.done) {
      clearInterval(poll);
      showResults(data.results);
    }
  }, 3000);
}
```

Alternatively, replace polling with **Server-Sent Events (SSE)** — the Flask route pushes `data:` lines as each rule completes, and `EventSource` in the browser receives them without repeated HTTP round-trips.

```python
# SSE endpoint (Flask streaming response)
@bp.get("/batch/job/<job_id>/stream")
def stream_batch(job_id):
    def generate():
        result = celery_app.GroupResult.restore(job_id)
        seen = set()
        while not result.ready():
            for r in result.results:
                if r.ready() and r.id not in seen:
                    seen.add(r.id)
                    yield f"data: {json.dumps(r.result)}\n\n"
            time.sleep(1)
        yield "data: {\"done\": true}\n\n"
    return Response(generate(), mimetype="text/event-stream")
```

---

### Infrastructure required

| Component | Dev | Production |
|---|---|---|
| Message broker | Redis (Docker) | Azure Cache for Redis / Service Bus |
| Result backend | Redis | Azure Cache for Redis |
| Worker process | `celery -A app.tasks.batch_tasks worker` | Containerized worker (Kubernetes Job / ACI) |
| Monitoring | Flower (`celery flower`) | Azure Monitor + Application Insights |
| Concurrency | `--concurrency=4` Celery option | Scale worker replicas horizontally |

**Docker Compose addition:**
```yaml
services:
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  worker:
    build: .
    command: celery -A app.tasks.batch_tasks worker --loglevel=info --concurrency=4
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
    depends_on: [redis, db]
```

---

### Decision guide

| Scenario | Recommendation |
|---|---|
| < 10 rules, < 30 s total | `ThreadPoolExecutor` — minimal change, no new infra |
| 10–50 rules or month-end | Celery + Redis, polling UI (3 s interval) |
| 50+ rules or SLA < 10 s response | Celery group + SSE streaming status screen |
| Scheduled overnight run | APScheduler or Celery beat (no human waiting) |

---

## Stored Procedure Implementation Consideration

The current allocation engine runs in Python/pandas (in-process). For production on a scalable RDBMS such as **PostgreSQL** or **Oracle**, pushing the shredding logic into the database as a stored procedure eliminates row-by-row Python overhead, network round-trips for large datasets, and ORM overhead — all data movement stays inside the DB engine.

---

### Why stored procedures for an allocation engine

| Concern | Python/pandas (current) | Stored procedure (target) |
|---|---|---|
| 10 M instrument rows | Pulls all rows into memory | Set-based `INSERT … SELECT` — never leaves DB |
| Network cost | Rows travel app → DB twice (read + write) | Zero network transfer |
| Parallelism | Python GIL limits threads | DB executor can parallel-scan and parallel-insert |
| Atomicity | Explicit `db.session.commit()` | Wrapped in a single DB transaction block |
| Auditing | Python logs | `BEGIN`/`COMMIT` visible in DB audit trail |
| Hot deployment | Code redeploy required | `REPLACE PROCEDURE` with no app restart |

---

### PostgreSQL — `PL/pgSQL` stored procedure

```sql
-- migrations/V010__sp_run_allocation.sql
CREATE OR REPLACE PROCEDURE sp_run_allocation(
    p_rule_id    INTEGER,
    p_as_of_date DATE,
    p_run_by     VARCHAR(50),
    OUT p_batch_run_id UUID,
    OUT p_output_rows  INTEGER,
    OUT p_orphan_rows  INTEGER
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_rule          allocation_rule%ROWTYPE;
    v_batch_run_id  UUID := gen_random_uuid();
    v_started_at    TIMESTAMP := NOW();
BEGIN
    -- 1. Load rule definition
    SELECT * INTO v_rule FROM allocation_rule WHERE id = p_rule_id AND is_active = TRUE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Rule % not found or inactive', p_rule_id;
    END IF;

    -- 2. Register batch run
    INSERT INTO batch_run (id, rule_id, as_of_date, status, started_at, run_by)
    VALUES (v_batch_run_id, p_rule_id, p_as_of_date, 'RUNNING', v_started_at, p_run_by);

    -- 3. DEBIT entries: source JOIN lookup → output
    INSERT INTO fct_mgmt_ledger
        (id, as_of_date, account_id, cost_centre, product, amount, entry_type, batch_run_id)
    SELECT
        gen_random_uuid(),
        p_as_of_date,
        r.output_account_id,
        r.output_cost_centre,
        src.product,
        src.balance,
        'DEBIT',
        v_batch_run_id
    FROM proc_inst_data  src
    JOIN ref_static_allocation r
      ON src.customer_id = r.customer_id
    WHERE src.as_of_date = p_as_of_date;

    GET DIAGNOSTICS p_output_rows = ROW_COUNT;

    -- 4. CREDIT offset entries
    INSERT INTO fct_mgmt_ledger
        (id, as_of_date, account_id, cost_centre, product, amount, entry_type, batch_run_id)
    SELECT
        gen_random_uuid(),
        p_as_of_date,
        r.offset_account_id,
        r.output_cost_centre,
        src.product,
        -src.balance,
        'CREDIT',
        v_batch_run_id
    FROM proc_inst_data  src
    JOIN ref_static_allocation r
      ON src.customer_id = r.customer_id
    WHERE src.as_of_date = p_as_of_date;

    -- 5. Orphan count (rows with no lookup match)
    SELECT COUNT(*) INTO p_orphan_rows
    FROM proc_inst_data src
    LEFT JOIN ref_static_allocation r ON src.customer_id = r.customer_id
    WHERE src.as_of_date = p_as_of_date AND r.customer_id IS NULL;

    -- 6. Close batch run
    UPDATE batch_run
    SET status       = 'COMPLETED',
        output_row_count = p_output_rows,
        orphan_count     = p_orphan_rows,
        completed_at     = NOW()
    WHERE id = v_batch_run_id;

    p_batch_run_id := v_batch_run_id;

EXCEPTION WHEN OTHERS THEN
    UPDATE batch_run
    SET status = 'FAILED', error_message = SQLERRM, completed_at = NOW()
    WHERE id = v_batch_run_id;
    RAISE;
END;
$$;
```

---

### Oracle — `PL/SQL` equivalent

```sql
-- Oracle: same logic, Oracle syntax
CREATE OR REPLACE PROCEDURE sp_run_allocation(
    p_rule_id       IN  NUMBER,
    p_as_of_date    IN  DATE,
    p_run_by        IN  VARCHAR2,
    p_batch_run_id  OUT VARCHAR2,
    p_output_rows   OUT NUMBER,
    p_orphan_rows   OUT NUMBER
)
AS
    v_batch_run_id VARCHAR2(36) := LOWER(RAWTOHEX(SYS_GUID()));
    v_err_msg      VARCHAR2(4000);
BEGIN
    INSERT INTO batch_run (id, rule_id, as_of_date, status, started_at, run_by)
    VALUES (v_batch_run_id, p_rule_id, p_as_of_date, 'RUNNING', SYSDATE, p_run_by);

    INSERT INTO fct_mgmt_ledger (id, as_of_date, account_id, cost_centre, product, amount, entry_type, batch_run_id)
    SELECT SYS_GUID(), p_as_of_date, r.output_account_id, r.output_cost_centre,
           src.product, src.balance, 'DEBIT', v_batch_run_id
    FROM proc_inst_data src
    JOIN ref_static_allocation r ON src.customer_id = r.customer_id
    WHERE src.as_of_date = p_as_of_date;

    p_output_rows := SQL%ROWCOUNT;

    -- credit entries ...

    SELECT COUNT(*) INTO p_orphan_rows
    FROM proc_inst_data src
    LEFT JOIN ref_static_allocation r ON src.customer_id = r.customer_id
    WHERE src.as_of_date = p_as_of_date AND r.customer_id IS NULL;

    UPDATE batch_run
    SET status = 'COMPLETED', output_row_count = p_output_rows,
        orphan_count = p_orphan_rows, completed_at = SYSDATE
    WHERE id = v_batch_run_id;

    COMMIT;
    p_batch_run_id := v_batch_run_id;

EXCEPTION WHEN OTHERS THEN
    v_err_msg := SUBSTR(SQLERRM, 1, 4000);
    UPDATE batch_run SET status = 'FAILED', error_message = v_err_msg, completed_at = SYSDATE
    WHERE id = v_batch_run_id;
    COMMIT;
    RAISE;
END sp_run_allocation;
/
```

---

### Python framework for calling stored procedures

Replace the pandas logic in `allocation_engine.py` with a thin SP dispatcher. The Python layer becomes orchestration only — auth, parameter validation, result surfacing.

```python
# app/services/sp_engine.py
"""
Stored-procedure dispatch layer.
Replaces the pandas shredding loop when running on PostgreSQL or Oracle.
"""
from __future__ import annotations
import uuid
from datetime import date
from dataclasses import dataclass
from app.models import db
from app.models.workflow import BatchRun

# ── Dialect registry ──────────────────────────────────────────────────────────
_SP_CALL: dict[str, str] = {
    # dialect  : CALL syntax
    "postgresql": "CALL sp_run_allocation(:rule_id, :as_of_date, :run_by, NULL, NULL, NULL)",
    "oracle":     "BEGIN sp_run_allocation(:rule_id, :as_of_date, :run_by, :batch_run_id, :output_rows, :orphan_rows); END;",
}

@dataclass
class SpResult:
    batch_run_id: str
    output_rows:  int
    orphan_rows:  int
    status:       str


def run_rule_via_sp(rule_id: int, as_of_date: date, run_by: str) -> SpResult:
    """
    Call the database stored procedure for a single allocation rule.
    Works on PostgreSQL (psycopg2 / asyncpg) and Oracle (cx_Oracle / oracledb).
    """
    dialect = db.engine.dialect.name          # "postgresql" | "oracle" | "sqlite"
    if dialect not in _SP_CALL:
        raise NotImplementedError(f"SP dispatch not supported for dialect: {dialect}")

    sql = _SP_CALL[dialect]

    with db.engine.begin() as conn:           # auto-commit on exit
        if dialect == "postgresql":
            # psycopg2 returns OUT params as a result row for CALL
            result = conn.execute(
                db.text(sql),
                {"rule_id": rule_id, "as_of_date": as_of_date, "run_by": run_by},
            )
            row = result.fetchone()
            batch_run_id = str(row[0]) if row else str(uuid.uuid4())
            output_rows  = int(row[1]) if row else 0
            orphan_rows  = int(row[2]) if row else 0

        elif dialect == "oracle":
            # cx_Oracle / python-oracledb: use out-bind variables
            import oracledb
            raw_conn = conn.connection.dbapi_connection
            cursor   = raw_conn.cursor()
            b_id     = cursor.var(oracledb.STRING)
            b_out    = cursor.var(oracledb.NUMBER)
            b_orp    = cursor.var(oracledb.NUMBER)
            cursor.execute(
                "BEGIN sp_run_allocation(:1,:2,:3,:4,:5,:6); END;",
                [rule_id, as_of_date, run_by, b_id, b_out, b_orp],
            )
            batch_run_id = b_id.getvalue()
            output_rows  = int(b_out.getvalue() or 0)
            orphan_rows  = int(b_orp.getvalue() or 0)

    # Refresh Python-side BatchRun from what the SP wrote
    run = db.session.get(BatchRun, batch_run_id)
    return SpResult(
        batch_run_id=batch_run_id,
        output_rows=output_rows,
        orphan_rows=orphan_rows,
        status=run.status if run else "UNKNOWN",
    )
```

**Plugging it into the batch route / Celery task:**

```python
# In app/routes/api.py (or batch_tasks.py)
from app.config import settings
from app.services import allocation_engine, sp_engine

def run_rule(rule_id: int, as_of_date: date, run_by: str):
    """Dispatch to SP engine on enterprise DB, Python engine on SQLite/dev."""
    if settings.USE_SP_ENGINE:                # env var: USE_SP_ENGINE=1
        return sp_engine.run_rule_via_sp(rule_id, as_of_date, run_by)
    return allocation_engine.run_rule(rule_id, as_of_date, run_by)
```

Set `USE_SP_ENGINE=1` in production Docker / Kubernetes env and `USE_SP_ENGINE=0` (default) in dev/test — no code path changes required.

---

### Parallel SP execution (combines with Batch Parallel consideration above)

```python
# Fan out one SP call per rule_id, same ThreadPoolExecutor pattern
from concurrent.futures import ThreadPoolExecutor, as_completed

def run_batch_via_sp(rule_ids: list[int], as_of_date: date, run_by: str, max_workers: int = 8):
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(sp_engine.run_rule_via_sp, rid, as_of_date, run_by): rid
                   for rid in rule_ids}
        for future in as_completed(futures):
            rid = futures[future]
            try:
                results[rid] = future.result()
            except Exception as exc:
                results[rid] = SpResult(batch_run_id="", output_rows=0,
                                        orphan_rows=0, status=f"FAILED: {exc}")
    return results
```

The DB itself can also parallelize — on **PostgreSQL** enable `max_parallel_workers_per_gather` so each SP's `INSERT … SELECT` uses multiple workers. On **Oracle** use `PARALLEL` hint:
```sql
INSERT /*+ PARALLEL(fct_mgmt_ledger, 4) */ INTO fct_mgmt_ledger ...
SELECT /*+ PARALLEL(src, 4) PARALLEL(r, 4) */ ...
```

---

### Migration strategy (Python → SP)

| Phase | Action |
|---|---|
| 1 — Baseline | Keep Python engine as-is; add `USE_SP_ENGINE` flag (default off) |
| 2 — Write SP | Author `sp_run_allocation` in a Flyway / Alembic migration SQL file |
| 3 — Shadow run | Run both engines on the same date; assert output tables are identical |
| 4 — Cutover | Flip `USE_SP_ENGINE=1` in staging, then production |
| 5 — Retire | Remove pandas shredding code after 1 release cycle |

---

### SP management best practices

| Practice | Detail |
|---|---|
| Version every SP | Store in `migrations/` as `V0NN__sp_name.sql`; deploy via Flyway or Alembic `op.execute()` |
| Keep business logic out of SQL | Allocate in SP; orchestrate, auth, and surface in Python |
| Unit-test the SP | `pytest` fixture spins up a test DB; call SP; assert row counts and amounts |
| Grant minimum privilege | `GRANT EXECUTE ON sp_run_allocation TO bankpft_app_role` — no DML grants on base tables |
| Parameter validation | Validate `p_rule_id` and `p_as_of_date` in Python before the DB call — fail fast before the SP is invoked |

---

## Custom Stored Procedure Batch Runner

A **generic SP runner** allows any database stored procedure to be registered and executed through the same batch framework — without writing new Python engine code. This is useful for custom aggregations, regulatory extracts, inter-system feeds, or any process that a DBA already owns in SQL.

### Current Implementation (live)

The SP runner is **fully implemented** as a first-class batch step type:

| Component | Location | Description |
|---|---|---|
| `SpRun` model | `app/models/workflow.py` | Tracks every SP invocation: `sp_name`, `params_json`, `status` (`COMPLETED`/`FAILED`), `started_at`, `completed_at`, `run_by`, `error_message`, `exec_step_id` |
| `run_sp()` | `app/services/sp_runner.py` | Validates SP name, creates a `SpRun` record, calls `CALL sp_name(...)` via SQLAlchemy named binds synchronously, then marks the run `COMPLETED` or `FAILED` |
| SP Detail UI | `/batch/sp-runs/<run_id>` | Per-run timing, resolved parameters, and result/error panel — accessible via the Run ID link on the batch execution detail page |
| Batch integration | `app/services/batch_executor.py` | `CUSTOM_SP` steps call `run_sp()` inline; step becomes `COMPLETED` or `FAILED` just like any other step type |
| Integration tests | `tests/test_sp_integration.py` | 12 tests against live PostgreSQL covering SP catalog, run_sp lifecycle, token resolution, and error handling |
| DB objects | `db/procedures/`, `db/ddl/` | SQL files for the test SP (`sp_test_echo`) and a real-world template (`sp_month_end_sample.sql`) |

**SP name validation** rejects names with spaces, double-dashes, semicolons, or SQL injection sequences. Only `schema.proc_name` and `proc_name` forms are allowed.

---

### Extended SP Registry — Design Consideration

Beyond the allocation and FTP engines, a **SP job registry** (below) extends the runner to allow named jobs with parameter templates to be managed entirely through the UI \u2014 without any code changes per SP.

---

### Data model — `custom_sp_job`

```sql
-- migrations/V011__custom_sp_job.sql
CREATE TABLE custom_sp_job (
    id          SERIAL          PRIMARY KEY,
    name        VARCHAR(100)    NOT NULL UNIQUE,
    description TEXT,
    sp_name     VARCHAR(200)    NOT NULL,   -- fully-qualified: schema.sp_name
    params_json TEXT,                       -- JSON array of {name, type, value_expr}
    is_active   BOOLEAN         NOT NULL DEFAULT TRUE,
    created_by  VARCHAR(50),
    created_at  TIMESTAMP       DEFAULT NOW(),
    updated_at  TIMESTAMP       DEFAULT NOW()
);

CREATE TABLE custom_sp_run (
    id           UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id       INTEGER       NOT NULL REFERENCES custom_sp_job(id),
    as_of_date   DATE          NOT NULL,
    status       VARCHAR(20)   NOT NULL DEFAULT 'RUNNING',  -- RUNNING | COMPLETED | FAILED
    started_at   TIMESTAMP     DEFAULT NOW(),
    completed_at TIMESTAMP,
    run_by       VARCHAR(50)   NOT NULL,
    return_json  TEXT,         -- OUT params / result summary stored as JSON
    error_message TEXT
);
```

**SQLAlchemy models (`app/models/workflow.py` addition):**

```python
class CustomSpJob(db.Model):
    """Registry of custom stored procedures available as batch steps."""
    __tablename__ = "custom_sp_job"
    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name        = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    sp_name     = db.Column(db.String(200), nullable=False)   # e.g. "dbo.sp_regulatory_extract"
    params_json = db.Column(db.Text, nullable=True)           # JSON param spec (see below)
    is_active   = db.Column(db.Boolean, default=True)
    created_by  = db.Column(db.String(50), nullable=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    runs        = db.relationship("CustomSpRun", backref="job", lazy="dynamic")


class CustomSpRun(db.Model):
    """Execution record for a single custom SP job invocation."""
    __tablename__ = "custom_sp_run"
    id           = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id       = db.Column(db.Integer, db.ForeignKey("custom_sp_job.id"), nullable=False)
    as_of_date   = db.Column(db.Date, nullable=False)
    status       = db.Column(db.String(20), default="RUNNING")
    started_at   = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    run_by       = db.Column(db.String(50), nullable=False)
    return_json  = db.Column(db.Text, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
```

---

### Parameter specification (`params_json`)

Each job stores its parameter list as a JSON array. `value_expr` can be a literal or one of the built-in tokens (`{as_of_date}`, `{run_by}`, `{run_id}`) that the runner substitutes at call time.

```json
[
  { "name": "p_as_of_date", "type": "date",    "value_expr": "{as_of_date}" },
  { "name": "p_entity_id",  "type": "integer", "value_expr": "10" },
  { "name": "p_run_by",     "type": "string",  "value_expr": "{run_by}" }
]
```

Supported `type` values: `"date"`, `"integer"`, `"float"`, `"string"`, `"boolean"`.

---

### Service layer (`app/services/sp_runner.py`)

```python
# app/services/sp_runner.py
"""Generic stored-procedure batch runner — independent of allocation and FTP engines."""
from __future__ import annotations
import json
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from app.models import db
from app.models.workflow import CustomSpJob, CustomSpRun

# ── Token substitution ────────────────────────────────────────────────────────
def _resolve_value(expr: str, context: dict) -> Any:
    """Replace {token} placeholders; cast to declared type."""
    return expr.format(**context)

_TYPE_CASTS = {
    "date":    lambda v: date.fromisoformat(v) if isinstance(v, str) else v,
    "integer": int,
    "float":   float,
    "string":  str,
    "boolean": lambda v: str(v).lower() in ("1", "true", "yes"),
}

def _build_params(params_spec: list[dict], context: dict) -> dict:
    params = {}
    for p in params_spec:
        raw   = _resolve_value(str(p.get("value_expr", "")), context)
        cast  = _TYPE_CASTS.get(p["type"], str)
        params[p["name"]] = cast(raw)
    return params

# ── Dialect-aware CALL builder ────────────────────────────────────────────────
def _build_call_sql(sp_name: str, params: dict, dialect: str) -> tuple[str, dict]:
    """Return (sql_string, bind_dict) for the target dialect."""
    named = {k: v for k, v in params.items()}
    if dialect == "postgresql":
        placeholders = ", ".join(f":{k}" for k in named)
        sql = f"CALL {sp_name}({placeholders})"
    elif dialect == "oracle":
        placeholders = ", ".join(f":{k}" for k in named)
        sql = f"BEGIN {sp_name}({placeholders}); END;"
    else:                 # sqlite / dev — raise clearly
        raise NotImplementedError(f"Custom SP runner not supported on dialect: {dialect}")
    return sql, named

# ── Main entry point ──────────────────────────────────────────────────────────
@dataclass
class SpRunResult:
    run_id:   str
    status:   str
    returned: dict = field(default_factory=dict)
    error:    str  = ""

def run_custom_sp(job_id: int, as_of_date: date, run_by: str) -> SpRunResult:
    """Execute a registered custom SP job and persist the run record."""
    job = db.session.get(CustomSpJob, job_id)
    if not job or not job.is_active:
        raise ValueError(f"CustomSpJob {job_id} not found or inactive")

    run_id  = str(uuid.uuid4())
    context = {
        "as_of_date": as_of_date.isoformat(),
        "run_by":     run_by,
        "run_id":     run_id,
    }

    # Persist RUNNING record
    sp_run = CustomSpRun(
        id=run_id, job_id=job_id, as_of_date=as_of_date,
        status="RUNNING", run_by=run_by,
    )
    db.session.add(sp_run)
    db.session.commit()

    params_spec = json.loads(job.params_json or "[]")
    params      = _build_params(params_spec, context)
    dialect     = db.engine.dialect.name

    try:
        sql, binds = _build_call_sql(job.sp_name, params, dialect)
        with db.engine.begin() as conn:
            result   = conn.execute(db.text(sql), binds)
            returned = dict(result.fetchone()._mapping) if result.returns_rows else {}

        sp_run.status       = "COMPLETED"
        sp_run.return_json  = json.dumps(returned)
        sp_run.completed_at = datetime.utcnow()
        db.session.commit()
        return SpRunResult(run_id=run_id, status="COMPLETED", returned=returned)

    except Exception as exc:
        sp_run.status        = "FAILED"
        sp_run.error_message = str(exc)
        sp_run.completed_at  = datetime.utcnow()
        db.session.commit()
        return SpRunResult(run_id=run_id, status="FAILED", error=str(exc))
```

---

### Route additions (`app/routes/batch.py`)

```python
from app.services.sp_runner import run_custom_sp
from app.models.workflow import CustomSpJob, CustomSpRun

@bp.route("/run-custom-sp", methods=["POST"])
@login_required
def run_custom_sp_batch():
    job_id    = request.form.get("job_id", type=int)
    as_of_str = request.form.get("as_of_date", "")
    if not job_id:
        flash("Please select a custom SP job.", "danger")
        return redirect(url_for("batch.list_batches"))
    try:
        as_of = datetime.strptime(as_of_str, "%Y-%m-%d").date() if as_of_str else date.today()
    except ValueError:
        flash("Invalid date. Use YYYY-MM-DD.", "danger")
        return redirect(url_for("batch.list_batches"))

    result = run_custom_sp(job_id, as_of, current_user.username)
    if result.status == "COMPLETED":
        flash(f"Custom SP completed. Returned: {result.returned}", "success")
    else:
        flash(f"Custom SP failed: {result.error}", "danger")
    return redirect(url_for("batch.custom_sp_run_detail", run_id=result.run_id))


@bp.route("/custom-sp/<run_id>")
@login_required
def custom_sp_run_detail(run_id):
    run = CustomSpRun.query.get_or_404(run_id)
    return render_template("batch/custom_sp_detail.html", run=run)
```

---

### REST API additions (`app/routes/api.py`)

```python
# GET  /api/v1/batch/custom-sp-jobs   — list registered jobs
# POST /api/v1/batch/custom-sp/run    — trigger a job
# GET  /api/v1/batch/custom-sp/<id>   — poll run status

@bp.get("/batch/custom-sp-jobs")
@api_login_required
def list_custom_sp_jobs():
    jobs = CustomSpJob.query.filter_by(is_active=True).all()
    return jsonify([{"id": j.id, "name": j.name, "sp_name": j.sp_name} for j in jobs])

@bp.post("/batch/custom-sp/run")
@api_login_required
def run_custom_sp_api():
    body     = request.get_json()
    job_id   = body.get("job_id")
    as_of    = date.fromisoformat(body.get("as_of_date", date.today().isoformat()))
    result   = run_custom_sp(job_id, as_of, g.current_user.username)
    code     = 200 if result.status == "COMPLETED" else 500
    return jsonify({"run_id": result.run_id, "status": result.status,
                    "returned": result.returned, "error": result.error}), code

@bp.get("/batch/custom-sp/<run_id>")
@api_login_required
def custom_sp_run_status(run_id):
    run = CustomSpRun.query.get_or_404(run_id)
    return jsonify({"run_id": run.id, "job_id": run.job_id,
                    "status": run.status, "as_of_date": str(run.as_of_date),
                    "return_json": json.loads(run.return_json or "{}"),
                    "error_message": run.error_message})
```

**Example curl calls:**

```bash
# List available custom SP jobs
curl -u admin:admin http://localhost:5000/api/v1/batch/custom-sp-jobs

# Trigger a custom SP job
curl -u admin:admin -X POST http://localhost:5000/api/v1/batch/custom-sp/run \
  -H "Content-Type: application/json" \
  -d '{"job_id": 1, "as_of_date": "2026-03-31"}'

# Poll run status
curl -u admin:admin http://localhost:5000/api/v1/batch/custom-sp/a3f9b1c2-...
```

---

### Admin UI — registering a new custom SP job

The existing admin pattern (user/group forms) is extended with a simple job registry form:

| Field | Input | Example |
|---|---|---|
| Name | Text | `REGULATORY_EXTRACT_MAS610` |
| Description | Textarea | `Monthly MAS 610 extract to reporting schema` |
| SP Name | Text | `reporting.sp_mas610_extract` |
| Parameters | JSON textarea | `[{"name":"p_as_of_date","type":"date","value_expr":"{as_of_date}"}]` |
| Active | Checkbox | ✓ |

Once registered, the job appears in the batch list UI alongside Allocation and FTP run options — same page, same "Run" button pattern.

---

### Key design principles

| Principle | Detail |
|---|---|
| Zero new engine code per SP | Register in the DB admin; the generic runner handles the call |
| Complete audit trail | Every invocation writes a `custom_sp_run` row with status, timestamps, `return_json`, and errors |
| Parameter injection safety | Parameters are bound via `db.text()` named binds — never string-interpolated into SQL |
| Dialect-aware | Works on PostgreSQL and Oracle; raises `NotImplementedError` clearly on SQLite/dev |
| Same batch UI/API surface | `CustomSpRun` appears in batch history alongside `BatchRun` and `FtpRun` |
| Separation of concerns | SP Runner knows nothing about allocation or FTP logic — it only calls, logs, and returns |

---

## Logging Framework — Implementation Consideration

The prototype writes ad-hoc log files per allocation batch run (`instance/batch_logs/batch_<id>.log`). A production deployment needs a **unified, structured logging framework** that separates three distinct log streams and routes each to the right destination.

---

### Three Log Streams

| Stream | What it records | Audience | Retention |
|---|---|---|---|
| **Processing Log** | Engine execution steps — row counts, join results, variance checks, timing | Ops / Support | 90 days per run; purge after |
| **Application Log** | Flask request/response, startup events, background job lifecycle, unhandled exceptions | DevOps | 30 days; ship to SIEM |
| **User Activity Log** | Who did what and when — logins, uploads submitted, rules created/edited, batches triggered, admin actions | Audit / Compliance | 7 years (regulatory) |

---

### Recommended Stack

| Layer | Technology | Notes |
|---|---|---|
| Structured formatting | Python `structlog` or `logging` + `python-json-logger` | Emit JSON per record — machine-readable by Splunk / ELK / Azure Monitor |
| Log transport | `logging.handlers.RotatingFileHandler` (local) → Fluentd / Filebeat sidecar → central store | Keep local buffer for resilience |
| Central store | Azure Monitor Log Analytics, Splunk, or ELK | Single query plane across all streams |
| Correlation ID | Inject `X-Request-Id` header on every request; attach to all log records in that request | Enables end-to-end trace across streams |

---

### Processing Log Design

Each batch execution creates a structured log file. In production replace the current flat text file with a DB table or append-only object-store blob:

```python
# app/services/batch_logger.py

import logging, json
from pathlib import Path

class BatchLogger:
    """Structured per-batch logger that writes JSON lines."""

    def __init__(self, batch_id: str, log_dir: str = "instance/batch_logs"):
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        self.path = Path(log_dir) / f"batch_{batch_id[:8]}.jsonl"
        self._logger = logging.getLogger(f"batch.{batch_id[:8]}")
        handler = logging.FileHandler(self.path)
        handler.setFormatter(logging.Formatter("%(message)s"))
        self._logger.addHandler(handler)
        self._logger.setLevel(logging.DEBUG)
        self.batch_id = batch_id

    def log(self, level: str, event: str, **kwargs):
        record = {"batch_id": self.batch_id, "level": level, "event": event, **kwargs}
        self._logger.info(json.dumps(record))

    def start(self, rule_name: str, user: str):
        self.log("START", "batch_started", rule=rule_name, user=user)

    def data(self, table: str, rows: int):
        self.log("DATA", "rows_loaded", table=table, rows=rows)

    def summary(self, src: int, out: int, orphans: int, variance: float):
        self.log("SUMMARY", "batch_complete",
                 src_rows=src, out_rows=out, orphans=orphans, variance=variance)

    def error(self, msg: str):
        self.log("ERROR", "batch_failed", error=msg)
```

**Sample JSON-line output:**
```json
{"batch_id": "a3f9b1c2", "level": "START",   "event": "batch_started", "rule": "Customer Shred", "user": "admin"}
{"batch_id": "a3f9b1c2", "level": "DATA",    "event": "rows_loaded",   "table": "proc_inst_data", "rows": 1200}
{"batch_id": "a3f9b1c2", "level": "SUMMARY", "event": "batch_complete","src_rows": 1200, "out_rows": 2400, "orphans": 0, "variance": 0.0}
```

---

### User Activity Log Design

Every user-driven mutation should emit a structured audit record **before** the DB write commits, so the audit trail is never lost even if the application crashes after writing:

```python
# app/services/audit_log.py

import json, logging
from datetime import datetime

_audit = logging.getLogger("audit")

def log_action(
    user: str,
    action: str,           # e.g. "UPLOAD_SUBMIT", "RULE_CREATE", "BATCH_TRIGGER"
    resource_type: str,    # e.g. "upload_batch", "allocation_rule"
    resource_id: str,
    detail: dict | None = None,
    ip_address: str | None = None,
):
    record = {
        "timestamp":     datetime.utcnow().isoformat() + "Z",
        "user":          user,
        "action":        action,
        "resource_type": resource_type,
        "resource_id":   str(resource_id),
        "detail":        detail or {},
        "ip":            ip_address,
    }
    _audit.info(json.dumps(record))
```

**Audit-worthy actions in this system:**

| Action constant | Trigger |
|---|---|
| `LOGIN_SUCCESS` / `LOGIN_FAIL` | `/auth/login` |
| `LOGOUT` | `/auth/logout` |
| `PASSWORD_CHANGE` | `/auth/change-password` |
| `UPLOAD_SUBMIT` | Maker submits an upload for approval |
| `UPLOAD_APPROVE` / `UPLOAD_REJECT` | Checker approves or rejects |
| `RULE_CREATE` / `RULE_UPDATE` / `RULE_DELETE` | Allocation rule mutations |
| `BATCH_TRIGGER` | Any batch execution started |
| `ADMIN_USER_CREATE` / `ADMIN_USER_UPDATE` | Admin manages users |
| `ADMIN_GROUP_CHANGE` | Admin changes group membership |
| `API_CALL` | Each authenticated API request (action + endpoint) |

**Flask integration — attach to every request in `app/__init__.py`:**
```python
@flask_app.before_request
def _attach_request_id():
    from uuid import uuid4
    g.request_id = request.headers.get("X-Request-Id", str(uuid4()))

@flask_app.after_request
def _log_request(response):
    from app.services.audit_log import log_action
    if current_user.is_authenticated:
        log_action(
            user=current_user.username,
            action="HTTP_REQUEST",
            resource_type="route",
            resource_id=request.endpoint or "",
            detail={"method": request.method, "status": response.status_code,
                    "path": request.path},
            ip_address=request.remote_addr,
        )
    return response
```

---

### Log Configuration (production `logging.ini`)

```ini
[loggers]
keys=root,audit,batch,app

[handlers]
keys=console,audit_file,batch_rotating,app_rotating

[formatters]
keys=json

[formatter_json]
class=pythonjsonlogger.jsonlogger.JsonFormatter
format=%(asctime)s %(name)s %(levelname)s %(message)s

[handler_console]
class=StreamHandler
formatter=json
args=(sys.stderr,)

[handler_audit_file]
class=logging.handlers.TimedRotatingFileHandler
formatter=json
args=('logs/audit.jsonl', 'midnight', 1, 2555)  # 7-year retention

[handler_batch_rotating]
class=logging.handlers.RotatingFileHandler
formatter=json
args=('logs/batch.jsonl', 'a', 52428800, 5)      # 50 MB × 5 files

[handler_app_rotating]
class=logging.handlers.RotatingFileHandler
formatter=json
args=('logs/app.jsonl', 'a', 52428800, 10)

[logger_audit]
level=INFO
handlers=audit_file
qualname=audit
propagate=0

[logger_batch]
level=DEBUG
handlers=batch_rotating
qualname=batch
propagate=0

[logger_app]
level=WARNING
handlers=app_rotating,console
qualname=app
propagate=0
```

---

### Log Shipping to Azure Monitor (optional)

```python
# requirements additions
opencensus-ext-azure==1.1.*
azure-monitor-opentelemetry==1.3.*

# in create_app():
from azure.monitor.opentelemetry import configure_azure_monitor
configure_azure_monitor(
    connection_string=os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"]
)
```

Azure Monitor then provides KQL queries across all three log streams:
```kql
// Failed batches in last 24 hours
customEvents
| where timestamp > ago(24h)
| where name == "batch_failed"
| project timestamp, user=customDimensions["user"], error=customDimensions["error"]
| order by timestamp desc
```

---

## Exception & Error Handling Framework — Implementation Consideration

The prototype relies on Flask's default exception handling (debug stack traces in dev, generic 500 in prod). A production allocation engine needs a **layered error handling strategy** that distinguishes business errors from system errors, centralises handling, and guarantees nothing is silently swallowed.

---

### Error Classification

| Category | Examples | Behaviour |
|---|---|---|
| **Validation Error** | Missing required field, bad date format, unknown format_id | HTTP 400; return `{"error": "..."}` immediately; no logging to error stream |
| **Business Rule Error** | Allocation ratios don't sum to 1.0, lookup table empty, orphan threshold exceeded | HTTP 422; log to processing log with context; surface to user |
| **Not Found** | Rule ID does not exist, file not in inbox | HTTP 404; minimal log |
| **Authorization Error** | Checker trying to approve own upload, non-admin accessing admin route | HTTP 403; log to audit stream |
| **Engine / Unexpected Error** | Pandas exception, DB integrity error, OS error | HTTP 500; log full traceback with `correlation_id`; alert ops |
| **External System Error** | Stored procedure timeout, FTP server unreachable, S3 upload failed | HTTP 502/503; retry with back-off; log to app stream |

---

### Central Error Handler in Flask

```python
# app/errors.py

from flask import jsonify, current_app, g
import traceback, logging

log = logging.getLogger("app")


class BankPFTError(Exception):
    """Base class for all application-defined errors."""
    status_code = 500
    log_level   = logging.ERROR

    def __init__(self, message: str, detail: dict | None = None):
        super().__init__(message)
        self.message = message
        self.detail  = detail or {}


class ValidationError(BankPFTError):
    status_code = 400
    log_level   = logging.DEBUG   # not worth an error-level log


class BusinessRuleError(BankPFTError):
    status_code = 422
    log_level   = logging.WARNING


class NotFoundError(BankPFTError):
    status_code = 404
    log_level   = logging.DEBUG


class AuthorizationError(BankPFTError):
    status_code = 403
    log_level   = logging.WARNING


class EngineError(BankPFTError):
    """Unexpected engine failure — triggers alert."""
    status_code = 500
    log_level   = logging.ERROR


class ExternalSystemError(BankPFTError):
    """Downstream dependency unavailable."""
    status_code = 503
    log_level   = logging.ERROR


def register_error_handlers(app):
    """Attach all error handlers to the Flask app."""

    @app.errorhandler(BankPFTError)
    def handle_app_error(exc: BankPFTError):
        log.log(exc.log_level, exc.message,
                extra={"detail": exc.detail,
                       "request_id": getattr(g, "request_id", None)})
        return jsonify({"error": exc.message, "detail": exc.detail}), exc.status_code

    @app.errorhandler(404)
    def handle_404(exc):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(405)
    def handle_405(exc):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(Exception)
    def handle_unexpected(exc):
        tb = traceback.format_exc()
        request_id = getattr(g, "request_id", "?")
        log.error("Unhandled exception", exc_info=True,
                  extra={"request_id": request_id, "traceback": tb})
        # Never expose internal detail to caller
        return jsonify({"error": "An internal error occurred",
                        "request_id": request_id}), 500
```

**Register in `create_app()`:**
```python
from app.errors import register_error_handlers
register_error_handlers(flask_app)
```

---

### Engine-Level Error Handling Pattern

Each engine (`allocation_engine.py`, `ftp_engine.py`, `batch_executor.py`) should follow the same pattern — catch narrowly, re-raise as a typed error, and always finalise the DB record:

```python
# app/services/allocation_engine.py  (pattern sketch)

from app.errors import EngineError, BusinessRuleError

def run_allocation(rule_id: int, as_of_date, run_by: str) -> BatchRun:
    batch = BatchRun(rule_id=rule_id, as_of_date=as_of_date,
                     run_by=run_by, status="RUNNING")
    db.session.add(batch)
    db.session.commit()

    try:
        _execute(batch, rule_id, as_of_date)
        batch.status = "COMPLETED"

    except BusinessRuleError:
        batch.status = "FAILED"
        batch.error_message = str(sys.exc_info()[1])
        raise                              # let caller surface to API/UI

    except Exception as exc:
        batch.status = "FAILED"
        batch.error_message = str(exc)
        raise EngineError(
            f"Allocation engine failed for rule {rule_id}: {exc}",
            detail={"rule_id": rule_id, "batch_id": batch.id}
        ) from exc

    finally:
        batch.completed_at = datetime.utcnow()
        db.session.commit()               # always save final status

    return batch
```

Key rules:
1. **Always commit the final `status` and `completed_at`** in `finally` — a crashed engine must never leave a `RUNNING` record.
2. **Never swallow exceptions silently** — `except Exception: pass` is forbidden.
3. **Wrap third-party exceptions** (`pandas`, `sqlalchemy`, `paramiko`) in typed `BankPFTError` subclasses so the central handler can classify them.

---

### API Error Response Contract

All API error responses follow a single envelope:

```json
{
  "error": "Human-readable summary",
  "detail": { "field": "as_of_date", "reason": "must be YYYY-MM-DD" },
  "request_id": "a3f9b1c2-..."
}
```

| HTTP Code | Error class | When |
|---|---|---|
| `400` | `ValidationError` | Missing / malformed request body field |
| `403` | `AuthorizationError` | Caller lacks permission for this action |
| `404` | `NotFoundError` | Referenced resource does not exist |
| `422` | `BusinessRuleError` | Request valid but engine rejected the data |
| `500` | `EngineError` or unhandled | Unexpected engine or server failure |
| `503` | `ExternalSystemError` | Stored procedure / external file system unavailable |

---

### Retry & Circuit Breaker (External Systems)

External calls (stored procedures, SFTP, object store) should use a retry decorator with exponential back-off, and a circuit breaker to avoid cascading failures:

```python
# app/utils/retry.py

import time, functools, logging

log = logging.getLogger("app")

def with_retry(max_attempts: int = 3, backoff_base: float = 2.0,
               retriable_exceptions: tuple = (OSError, TimeoutError)):
    """Decorator: retry on retriable exceptions with exponential back-off."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except retriable_exceptions as exc:
                    if attempt == max_attempts:
                        log.error("Max retries reached", extra={
                            "function": fn.__name__, "attempts": attempt, "error": str(exc)
                        })
                        raise
                    wait = backoff_base ** attempt
                    log.warning("Retrying after error", extra={
                        "function": fn.__name__, "attempt": attempt, "wait_s": wait
                    })
                    time.sleep(wait)
        return wrapper
    return decorator

# Usage:
# @with_retry(max_attempts=3, retriable_exceptions=(sqlalchemy.exc.OperationalError,))
# def call_stored_procedure(...): ...
```

---

### Architectural Governance

All architectural changes must be reviewed against the **System Integrity Matrix**. Any deviation from the established `BankPFTError` hierarchy or the `BatchRun` state machine requires a formal ADR (Architecture Decision Record) submission.

---

### AI Development & Copilot Usage

This project is optimized for AI-assisted development. Three core documents govern how the AI should build new features:

1. **[copilot-instructions.md](copilot-instructions.md)**: Strict PEP 8 rules, modern type-hinting, and Application Factory constraints.
2. **[docs/AI_DEVELOPMENT_GUIDE.md](docs/AI_DEVELOPMENT_GUIDE.md)**: Architectural patterns (JSON vs DB) and the Stored Procedure mandate.
3. **[development_prompt/](development_prompt/)**: A series of graduated prompts (1-12) that guide the AI through the application's entire development lifecycle, from Day 1 to Production Governance.

> [!TIP]
> **Building with Sophistication**: When asking an AI to extend the system, always reference **Prompt 12** to ensure it maintains the validation and observability standards required for a production-grade financial platform.

## License

MIT

---

### Dead-Letter Queue for Batch Steps

When a multi-task batch step fails, the step record in `batch_execution_step` acts as a **dead-letter entry**. A recovery job can query for stuck or failed steps and re-drive them:

```sql
-- Find steps that failed or are stuck RUNNING for > 10 minutes
SELECT e.id, e.definition_id, s.step_order, s.task_type, s.status, s.error_message
FROM   batch_execution e
JOIN   batch_execution_step s ON s.execution_id = e.id
WHERE  s.status IN ('FAILED', 'RUNNING')
  AND  (s.status = 'FAILED'
        OR s.started_at < NOW() - INTERVAL '10 minutes');
```

A recovery Flask CLI command can then re-run just the failed step:
```python
# flask recover-step <execution_id> <step_order>
```

---

### Summary — What to Build

| Component | Priority | Location |
|---|---|---|
| `app/errors.py` — typed exception hierarchy + central handlers | High | New file |
| `app/services/audit_log.py` — structured user activity logger | High | New file |
| `app/services/batch_logger.py` — JSON-line per-batch logger | Medium | Refactor existing log file writer |
| `app/utils/retry.py` — retry decorator for external calls | Medium | New file |
| `logging.ini` — three-stream handler configuration | High | Project root |
| `before_request` / `after_request` hooks — correlation ID + audit | Medium | `app/__init__.py` |
| CLI `recover-step` command — re-drive failed batch steps | Low | `app/commands.py` |

---

## AI Development & Copilot Usage
For engineers building new features using GitHub Copilot, Cursor, or Gemini, this project includes native system mapping instructions.
- Central system prompt constraints are defined in `copilot-instructions.md`.
- Deep architectural best-practices mapping out how to build iterative database components are defined in `docs/AI_DEVELOPMENT_GUIDE.md`.

Please ensure AI coding assistants strictly read and adhere to those guides to maintain structural uniformity.

## License

Prototype / Demo — not for production use.
