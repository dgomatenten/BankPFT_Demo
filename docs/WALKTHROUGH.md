# BankPFT — Screen-by-Screen Walkthrough

This guide walks through every screen in the Management Allocation System, explaining what each page does and how to use it.

---

## Table of Contents

1. [Login](#1-login)
2. [Dashboard](#2-dashboard)
3. [Data Upload — List](#3-data-upload--list)
4. [Data Upload — New Upload](#4-data-upload--new-upload)
5. [Data Upload — Detail & Maker/Checker](#5-data-upload--detail--makechecker)
6. [Allocation Rules — List](#6-allocation-rules--list)
7. [Allocation Rules — New Rule](#7-allocation-rules--new-rule)
8. [Allocation Rules — Entry Mode](#8-allocation-rules--entry-mode)
9. [Allocation Rules — Source Dimension Filters](#9-allocation-rules--source-dimension-filters)
10. [Allocation Rules — Debit & Credit Dimension Mapping](#10-allocation-rules--debit--credit-dimension-mapping)
11. [Allocation Rules — Data Filter Editor](#11-allocation-rules--data-filter-editor)
12. [Allocation Rules — Detail](#12-allocation-rules--detail)
13. [Allocation Rules — Edit Rule](#13-allocation-rules--edit-rule)
14. [Allocation Rules — Import from JSON](#14-allocation-rules--import-from-json)
15. [Batch Execution](#15-batch-execution)
16. [Batch Execution — Detail](#16-batch-execution--detail)
17. [Fund Transfer Pricing — Dashboard](#17-fund-transfer-pricing--dashboard)
18. [Fund Transfer Pricing — Product Config](#18-fund-transfer-pricing--product-config)
19. [Fund Transfer Pricing — Interest Rates Browser](#19-fund-transfer-pricing--interest-rates-browser)
20. [Fund Transfer Pricing — Run Detail](#20-fund-transfer-pricing--run-detail)
21. [Reports — Index](#21-reports--index)
22. [Management Ledger Report](#22-management-ledger-report)
23. [Operations Report](#23-operations-report)
24. [Database Table Browser](#24-database-table-browser)
25. [Table Browser — Data View](#25-table-browser--data-view)
26. [Test Data Generator](#26-test-data-generator)
27. [User Management](#27-user-management)
28. [Group Management](#28-group-management)
29. [Starting the Application](#29-starting-the-application)
30. [PWA — Install as Standalone App](#30-pwa--install-as-standalone-app)

---

## 1. Login

**URL:** `/auth/login`

The login page is displayed when accessing the system without authentication. All pages require a valid login.

**Key elements:**
- **Username** — enter your username
- **Password** — enter your password
- **Sign In** — authenticates and redirects to the Dashboard

**Default accounts** (password = username):

| Username | Role | Permissions |
|---|---|---|
| `admin` | Administrator | Make + Check + Admin |
| `maker1` | Maker | Create and submit uploads |
| `checker1` | Checker | Approve/reject uploads |

After login, the sidebar shows your display name, role badges (Maker/Checker/Admin), and links to change password or logout.

---

## 2. Dashboard

**URL:** `/`

The dashboard is the landing page. It provides a quick overview of the system's current state.

![Dashboard](images/01_dashboard.png)

**Key elements:**
- **Summary cards** — counts of Recent Uploads, Active Rules, Batch Runs, and Ledger Records
- **Recent Uploads** — last uploaded files with status badges (DRAFT, PENDING, APPROVED, PROCESSED)
- **Recent Batch Runs** — latest allocation batch runs with row counts

Use the sidebar navigation on the left to reach any module. Admin users will see additional **Users** and **Groups** links.

---

## 3. Data Upload — List

**URL:** `/upload`

Shows all upload batches sorted by date, with their current workflow status.

![Upload List](images/02_upload_list.png)

**Key elements:**
- **File name** — links to the upload detail page
- **Type** — INSTRUMENT, GL, or ALLOCATION
- **Status** — current Maker/Checker workflow state
- **Rows / Errors** — row count and validation error count
- **Maker / Checker** — who uploaded and who approved
- **Delete** — available for DRAFT or REJECTED batches only

Click any file name to view details, or click **New Upload** to upload a file.

---

## 4. Data Upload — New Upload

**URL:** `/upload/new`

Upload an Excel (.xlsx) or CSV file for validation and staging.

![New Upload](images/03_upload_new.png)

**How to use:**
1. **Select Data Type** — choose from the dropdown (Instrument Data, General Ledger, Allocation Ratios). These options are driven by `upload_config.json`
2. **Choose File** — select a `.xlsx` or `.csv` file from your computer
3. **Click Upload & Validate** — the file is parsed, validated against configured rules, and staged. The logged-in user is automatically recorded as the Maker

**Expected Column Headers** — shown at the bottom of the page, generated automatically from the JSON config. Required columns are in bold; optional columns are shown in italics.

After upload, you are redirected to the detail page showing validation results.

---

## 5. Data Upload — Detail & Maker/Checker

**URL:** `/upload/<batch_id>`

Shows upload details, validation results, and the Maker/Checker workflow.

![Upload Detail](images/12_upload_detail.png)

**Key elements:**
- **Workflow progress bar** — shows the current state: DRAFT → PENDING → APPROVED → PROCESSED
- **Batch info** — ID, type, status, row count, error count, maker, checker
- **Staged Data Preview** — first 20 rows of the uploaded data
- **Action buttons** (below preview, not shown):
  - **Submit for Review** — Maker submits (DRAFT → PENDING)
  - **Approve / Reject** — Checker reviews (PENDING → APPROVED or REJECTED)
  - **Process** — promotes staging data to processing tables (APPROVED → PROCESSED)

**4-Eyes Rule:** The Checker must be a different user than the Maker, and must belong to a group with the **Can Check** permission. The system enforces both constraints.

---

## 6. Allocation Rules — List

**URL:** `/rules`

Shows all allocation rules with their active/inactive status.

![Rules List](images/04_rules_list.png)

**Key elements:**
- **Rule name** — links to the rule detail page
- **Source / Lookup / Output tables** — the tables this rule operates on
- **Join Key** — the column used to match source data with allocation ratios
- **Status** — ACTIVE or INACTIVE
- **Edit** (pencil icon) — open the rule's edit form with all fields pre-populated
- **Toggle / Delete** — activate/deactivate or remove a rule

Rules are immediately active when created (no Maker/Checker workflow for rules).

---

## 7. Allocation Rules — New Rule

**URL:** `/rules/new`

Create a new allocation rule. The form is organised into five sections.

![New Rule](images/05_rules_new.png)

**How to use:**
1. **Rule Name / Description** — name and optional notes
2. **Source Table** — processed data table to read from
3. **Lookup Table** — allocation ratio table to join with
4. **Output Table** — where to write allocated results (`fct_mgmt_instrument` recommended)
5. **Join Key** — column linking source to lookup (e.g. `customer_id`)
6. **Entry Mode** — choose BOTH, Debit only, or Credit only (see section 8)
7. **Source Dimension Filters** — per-dimension member filter (see section 9)
8. **Debit & Credit Dimension Mapping** — per-dimension output value control (see section 10)
9. **Data Filters** — row-level filter conditions (see section 11)
10. **Click Create Rule** — saved immediately as ACTIVE

All dropdown options are driven by `rule_config.json`.

---

## 8. Allocation Rules — Entry Mode

**Location:** New Rule form — "Entry Mode" card

Controls which accounting entries the allocation engine generates for each matched row.

**Options:**

| Setting | Effect |
|---|---|
| **Both** (default) | Two rows per matched record: a **DEBIT** (target dimensions + positive balance) and a **CREDIT** (source/configured dimensions + negative balance) |
| **Debit only** | Single **DEBIT** row per matched record — balance moves to the target with no reversal |
| **Credit only** | Single **CREDIT** row per matched record — reversal posted without a corresponding debit entry |

**Example output for a 40% allocation, balance = 1000, mode = Both:**

| entry_type | account | org_unit | allocated_balance |
|---|---|---|---|
| DEBIT | ACT-001 | OU_TARGET | +400 |
| CREDIT | GL-CLR-8000 | OU_SOURCE | −400 |

> **Visibility:** Selecting **Debit only** hides the Credit Entry Dimension Mapping card. Selecting **Credit only** hides the Debit Entry Dimension Mapping card. **Both** shows both cards simultaneously.

---

## 9. Allocation Rules — Source Dimension Filters

**Location:** New Rule form — "Source Dimension Filters" card

For each dimension column in the selected source table, you can restrict which dimension members are included in the allocation run.

**Modes per dimension:**

| Mode | Behaviour |
|---|---|
| **All Members** (default) | All values of this dimension are included |
| **Specific Members** | Only rows whose dimension value appears in the comma-separated members list are included |

**Example — include only LOAN and DEPOSIT products:**

| Dimension | Mode | Members |
|---|---|---|
| Account ID | All Members | — |
| Customer ID | All Members | — |
| Product Code | Specific Members | `LOAN, DEPOSIT` |
| Org Unit | All Members | — |

Stored as `source_dim_json` in the database.

---

## 10. Allocation Rules — Debit & Credit Dimension Mapping

**Location:** New Rule form — "Debit Entry — Dimension Mapping" (green) and "Credit Entry — Dimension Mapping" (yellow) cards

Each entry type has its own independent dimension mapping table. The **Debit** card controls where allocated balances are posted; the **Credit** card controls where the equal-and-opposite reversal is posted. Card visibility follows the **Entry Mode** setting: the Debit card is hidden when **Credit only** is selected; the Credit card is hidden when **Debit only** is selected.

**Modes per dimension (same for both Debit and Credit):**

| Mode | Behaviour |
|---|---|
| **Same as Source** (default) | Copies the source dimension value to the output row |
| **From Lookup** | Reads the value from a column in the joined lookup table (e.g. `target_org_unit_id`) |
| **Fixed Value** | Writes a hardcoded value to every output row for this dimension |

**Typical configuration:**

*Debit — remap org to allocation target, keep other dimensions:*

| Dimension | Mode | Detail |
|---|---|---|
| Account ID | Same as Source | — |
| Org Unit | From Lookup | `target_org_unit_id` |
| Product Code | Same as Source | — |
| Customer ID | Same as Source | — |

*Credit — reverse at source org, post to GL clearing account:*

| Dimension | Mode | Detail |
|---|---|---|
| Account ID | Fixed Value | `GL-CLR-8000` |
| Org Unit | Same as Source | — |
| Product Code | Same as Source | — |
| Customer ID | Same as Source | — |

Debit mapping stored as `output_dim_json`; Credit mapping stored as `credit_dim_json`. Omitting `credit_dim_json` defaults all credit dimensions to **Same as Source**.

---

## 11. Allocation Rules — Data Filter Editor

**URL:** `/rules/new` (bottom of the form)

Row-level filter conditions that restrict which source rows are included when the allocation engine runs. Applied after source dimension filters.

![Filter Editor with Conditions](images/17_rule_filter_conditions.png)

**How to use:**
1. **Click "Add Condition"** — adds a new filter row
2. **Select Field** — dropdown shows filterable columns for the selected source table (from `filter_config.json`)
3. **Select Operator** — changes based on field type (string / numeric / date)
4. **Enter Value** — for `in`/`not in`, use comma-separated values; for `between`, use `min,max`
5. **Match Logic** — ALL conditions (AND) or ANY condition (OR)
6. **Remove** — click × to remove a condition

Filters are saved as JSON in `allocation_rule.filter_json` and applied at engine runtime.

---

## 12. Allocation Rules — Detail

**URL:** `/rules/<rule_id>`

View a rule's full configuration.

![Rule Detail with Filters](images/18_rule_detail_with_filters.png)

**Key elements:**
- Source / Lookup / Output table names
- **Entry Mode** badge — "DEBIT + CREDIT", "DEBIT only", or "CREDIT only"
- **Source Dimension Filters** card — shows mode and members per dimension
- **Debit Entry — Dimension Mapping** card (green) — shows mode and detail per dimension for DEBIT
- **Credit Entry — Dimension Mapping** card (yellow) — shows mode and detail per dimension for CREDIT; shows "same_as_source (default)" if not explicitly configured
- **Data Filters** card — shows saved filter conditions
- **Edit Rule** — opens the edit form with all fields pre-populated
- **Toggle / Delete** actions
- **Allocation ratios preview** — APPROVED ratios the rule would use

---

## 13. Allocation Rules — Edit Rule

**URL:** `/rules/<rule_id>/edit`

Edit all fields of an existing allocation rule. Accessible from:

- The **Edit** button (pencil icon) on the Rules List page
- The **Edit Rule** button in the Actions card on the Rule Detail page

**How to use:**

1. Open any rule from the list or detail page and click **Edit Rule**
2. All fields are pre-populated with the rule's current configuration
3. Dimension mapping tables (Source Filters, Debit Mapping, Credit Mapping) are rebuilt and restored to their saved state automatically
4. Data filter conditions are reloaded from the rule's saved filter configuration
5. Make any changes and click **Save Changes**

The rule is updated immediately and you are redirected back to the Detail page.

> **Note:** Editing a rule does not affect previously completed batch runs — historical results retain the configuration that was active at the time.

---

## 14. Allocation Rules — Import from JSON

**URL:** `/rules/import`

Create an allocation rule from a JSON file or pasted JSON text. Useful for version-controlling rule definitions or sharing configurations between environments.

![Rule Import from JSON](images/19b_rule_import.png)

**How to use:**
1. Click **Import JSON** from the Rules List page
2. Either **upload a `.json` file** or **paste JSON** into the text area
3. Click **Import Rule** — the rule is validated and saved

**Minimum required field:** `name`

**Full JSON schema:**

```json
{
  "name": "Customer Shred Q1",
  "description": "Optional notes",
  "source_table": "proc_inst_data",
  "lookup_table": "ref_static_allocation",
  "output_table": "fct_mgmt_instrument",
  "join_key": "customer_id",
  "entry_mode": "BOTH",
  "filter_json": {
    "logic": "AND",
    "conditions": [{"field": "product_code", "operator": "in", "value": "LOAN,DEPOSIT"}]
  },
  "source_dim_json": {
    "account_id":   {"mode": "all"},
    "org_unit_id":  {"mode": "all"},
    "product_code": {"mode": "specific", "members": ["LOAN", "DEPOSIT"]},
    "customer_id":  {"mode": "all"}
  },
  "output_dim_json": {
    "account_id":   {"mode": "same_as_source"},
    "org_unit_id":  {"mode": "lookup", "lookup_column": "target_org_unit_id"},
    "product_code": {"mode": "same_as_source"},
    "customer_id":  {"mode": "same_as_source"}
  },
  "credit_dim_json": {
    "account_id":   {"mode": "fixed", "value": "GL-CLR-8000"},
    "org_unit_id":  {"mode": "same_as_source"},
    "product_code": {"mode": "same_as_source"},
    "customer_id":  {"mode": "same_as_source"}
  }
}
```

Omitting `credit_dim_json` defaults all credit dimensions to **Same as Source**. Valid `entry_mode` values: `BOTH` (default), `DEBIT_ONLY`, `CREDIT_ONLY`.

### How the Rule Is Stored

After a successful import, the system redirects to the **Rule Detail** page. Every field from the JSON is persisted and displayed:

![Stored Rule Detail](images/19c_rule_stored_detail.png)

| Section | What is shown |
|---|---|
| **Header card** | ID, Name, Status (ACTIVE), Created By, Created timestamp |
| **Config row** | Source table, Lookup table, Output table, Entry Mode badge, Join Key(s) |
| **Description** | Free-text notes from the `description` field |
| **Source Dimension Filters** | One row per dimension — mode (`all` / `specific`) and any pinned members |
| **Debit Entry — Dimension Mapping** | Target dimension modes (`same_as_source`, `lookup`, `fixed`) with lookup column or fixed value |
| **Credit Entry — Dimension Mapping** | Same structure for the credit-side entry (only shown when `entry_mode` is `BOTH` or `CREDIT_ONLY`) |
| **Actions** | Edit Rule / Deactivate Rule / Delete Rule buttons |
| **Approved Allocation Ratios** | Pre-joined lookup rows that will be applied when the rule runs in a batch |

---

## 15. Batch Execution

**URL:** `/batch`

Run allocation rules or FTP calculations against processed data and view past run history.

![Batch Execution](images/06_batch_execution.png)

The page is divided into two run panels side-by-side and two separate history tables below.

### Run Allocation Batch

1. **Select a Rule** — choose from active allocation rules
2. **As-of Date** — the date to filter source data
3. **Click Run** — executes the Pandas-based allocation engine

**What happens during execution:**
1. Source data is loaded from the configured table (filtered by date)
2. **Data filters** (`filter_json`) are applied — rows not matching are dropped
3. **Source dimension filters** (`source_dim_json`) are applied per dimension
4. Allocation ratios are loaded from the lookup table (APPROVED status only)
5. A LEFT JOIN matches source rows to ratios by the rule's join key
6. For each matched row: `allocated_balance = source_balance × ratio`
7. If **entry_mode** = **BOTH** or **DEBIT_ONLY**: **DEBIT entry** — output dimensions resolved per `output_dim_json`
8. If **entry_mode** = **BOTH** or **CREDIT_ONLY**: **CREDIT entry** — dimensions resolved per `credit_dim_json` (defaults to same-as-source), balance = negative
9. **Orphan rows** (no matching ratio) — DEBIT only at source org (`default_ratio` from config)

### Run FTP Batch

1. **As-of Date** — the calculation date
2. **Click Run FTP** — triggers the FTP moving-average engine

**What the FTP engine does:**
1. Loads all active `ftp_product_config` records
2. For each distinct product, queries `proc_inst_data` for instruments on the as-of date
3. Computes the moving-average `base_rate` from approved interest rate history over the lookback window
4. Writes `base_rate` and `cost_of_fund = balance × base_rate × (days_in_month / days_in_year)` back to each instrument row

The **Allocation Batch History** and **FTP Run History** tables are shown separately below the run forms.

---

## 16. Batch Execution — Detail

**URL:** `/batch/<batch_id>`

View the full results of a completed batch run, including a granular processing log written by the engine.

![Batch Detail](images/14_batch_detail.png)

**Stats card fields:**

| Field | Description |
|---|---|
| **Batch ID** | UUID assigned to this run |
| **Status** | `RUNNING`, `COMPLETED`, or `FAILED` |
| **As-of Date** | The date used to filter source data |
| **Run By** | Username who triggered the batch |
| **Started** | Timestamp when the run began |
| **Source Rows** | Rows loaded from the source table after all filters |
| **Source Total** | Sum of the primary balance column from source data |
| **Output Rows** | Total rows written (DEBIT + CREDIT entries combined) |
| **Output Total** | Sum of allocated balances for DEBIT rows only |
| **Orphan Rows** | Source rows with no matching lookup ratio |
| **Variance** | `source_total − output_total` — should be 0 when ratios sum to 1.0 |

### Processing Log

Every engine run writes a timestamped log file to `instance/batch_logs/batch_<id>.log`. The full contents are displayed in a scrollable dark panel directly on the detail page.

![Batch Detail with Processing Log](images/14b_batch_detail_log.png)

**Log levels and what each line records:**

| Level | What is logged |
|---|---|
| `START` | Batch ID (first 8 chars) and user who triggered it |
| `RULE` | Rule name, source / lookup / output tables, entry mode, join key, dim config keys |
| `QUERY` | Table name and filter applied before each database read |
| `DATA` | Row count returned from each query |
| `FILTER` | Rows before → after each filter pass (data filter and source dim filter) |
| `JOIN` | Join key and type, plus matched vs orphan counts after the merge |
| `PROCESS` | Matched row count, emit flags, and final DEBIT / CREDIT entry counts |
| `ORPHAN` | Orphan row count and the default ratio applied |
| `DB` | Number of rows written to the output table |
| `SUMMARY` | Source rows, output rows, orphans, source total, output total, variance |
| `COMPLETE` | Total wall-clock time for the batch in seconds |
| `ERROR` / `FAILED` | Exception message if the run fails at any point |

The log file path (`batch_<id[:8]>.log`) is shown in the card header. Log files are stored at `instance/batch_logs/` and are never deleted automatically.

---

## 17. Fund Transfer Pricing — Dashboard

**URL:** `/ftp/`

The FTP dashboard is the entry point for all FTP operations.

![FTP Dashboard](images/19_ftp_dashboard.png)

**Key elements:**
- **Run FTP Calculation** form — select an as-of date and click **Run FTP** to trigger the engine
- **FTP Run History** table — lists past runs with status, instrument counts, and links to detail pages
- **FTP Config** button — navigate to the product config list
- **Interest Rates** button — open the rate browser
- **Upload Rates** button — shortcut to the Data Upload page (for uploading new rate files)

---

## 18. Fund Transfer Pricing — Product Config

**URL:** `/ftp/config`

Manage per-product FTP calculation parameters.

![FTP Config List](images/20_ftp_config_list.png)

**Config form fields:**

![FTP Config Form](images/21_ftp_config_form.png)

| Field | Description |
|---|---|
| **Product Code** | Must match a product in `dim_product` (e.g. `PROD-LON`) |
| **Method** | Calculation method — currently only `MOVING_AVG` is supported |
| **Rate Code** | Interest rate code to look up in `ref_interest_rate` (e.g. `SWAP_RATE`) |
| **Term / Mult** | Tenor of the rate point to use (e.g. `5 Y` = 5-year rate) |
| **Avg Period / Mult** | Length of the moving-average window (e.g. `3 M` = 3-month average) |
| **Active** | Whether this config is used in FTP runs |

The FTP engine skips any instrument whose product code has no active config — those instruments appear in the **Skipped** count on the run detail.

---

## 19. Fund Transfer Pricing — Interest Rates Browser

**URL:** `/ftp/rates`

Browse uploaded and approved interest rates with filtering.

![FTP Rates Browser](images/22_ftp_rates_list.png)

**Filters:** Date, Rate Code, Status (DRAFT / PENDING / APPROVED / REJECTED)

Rates are uploaded via the standard upload screen (Data Type: **Interest Rate**) and follow the DRAFT → PENDING → APPROVED workflow. Only APPROVED rates are used in FTP calculations.

**Expected Excel columns for Interest Rate upload:**

| Column | Type | Description |
|---|---|---|
| `effective_date` | date | Rate observation date |
| `interest_rate_code` | string | Rate identifier (e.g. `SWAP_RATE`) |
| `term` | integer | Tenor number (e.g. `3`) |
| `term_mult` | string | Tenor unit: D = day, M = month, Y = year |
| `rate` | float | Rate as decimal (e.g. `0.0535` = 5.35%) |

---

## 20. Fund Transfer Pricing — Run Detail

**URL:** `/ftp/run/<run_id>`

View details of a completed FTP run.

![FTP Run Detail](images/23_ftp_run_detail.png)

**Key elements:**
- Run metadata: as-of date, status, run by, timestamps
- **Instruments Processed** — total rows found for the as-of date
- **Instruments Matched** — rows where an active FTP config was found (base_rate/cost_of_fund written)
- **Instruments Skipped** — rows with no active FTP config for their product code
- Error message if the run failed

---

## 21. Reports — Index

**URL:** `/reports`

Hub page with links to all available reports.

![Reports Index](images/07_reports_index.png)

**Available reports:**
- **Management Ledger** — aggregated allocation results
- **Operations Report** — system activity summary
- **Database Table Browser** — browse and edit any database table
- **Execution Log** — linked from batch detail pages

**Available reports:**
- **Management Ledger** — aggregated allocation results
- **Operations Report** — system activity summary
- **Database Table Browser** — browse and edit any database table
- **Execution Log** — linked from batch detail pages

---

## 22. Management Ledger Report

**URL:** `/reports/ledger`

The primary output report.

![Management Ledger](images/08_mgmt_ledger.png)

**How to use:**
1. **Group By** — choose a dimension: Org Unit, Product, Customer
2. **Batch Run** — filter to a specific batch or view all
3. **Click Filter** — refresh the results

**Results table shows:**
- Dimension value (e.g., `target_org_unit_id`)
- **Total Balance** — sum of allocated balances
- **Total Income** — sum of allocated interest income
- **Row Count** — number of output records in the group

> **Tip:** To see only the net movement (DEBIT entries), filter by `entry_type = DEBIT` using the Table Browser. The CREDIT entries are the equal-and-opposite offset that confirms no balance is created.

---

## 23. Operations Report

**URL:** `/reports/operations`

System activity and health overview.

![Operations Report](images/09_operations.png)

**Key elements:**
- Upload activity by type and status
- Batch execution history
- Record counts across key tables
- System health indicators

---

## 24. Database Table Browser

**URL:** `/reports/tables`

Browse, search, and edit data in any database table.

![Table Browser](images/10_table_browser.png)

**How to use:**
1. **Select a table** from the dropdown
2. **Click Browse** — view the table's data with pagination

All tables are listed, including `fct_mgmt_instrument` for DEBIT/CREDIT entries, `ref_interest_rate` for rate curves, `ftp_product_config` for FTP settings, and `ftp_run` for FTP run history.

> **Access control:** **Edit** and **Delete** row actions are visible only to Admin users.

---

## 25. Table Browser — Data View

**URL:** `/reports/tables?table=<table_name>`

View table data with pagination and inline editing.

![Table Data View](images/15_table_browse_data.png)

**Key elements:**
- **Table selector** — switch between tables
- **Column headers** — all columns in the selected table
- **Data rows** — paginated (configurable page size)
- **Edit / Delete** — inline actions for each row (**Admin only**)
- **Pagination** — navigate through large tables

Useful for verifying dimension data, checking staged records, or inspecting DEBIT/CREDIT allocation entries.

---

## 26. Test Data Generator

**URL:** `/testdata`

Generate realistic test data for the system.

![Test Data Generator](images/11_testdata.png)

**Available generators:**

| Section | Generator | What it creates |
|---|---|---|
| Master Data | Generate Master Data | Dimension tables: Org Units, Products, Customers, Accounts |
| Instrument Data | Generate Instruments | 500+ instrument records in `proc_inst_data` (auto-approved) |
| Allocation Ratios | Generate Allocations (DB) | Allocation ratios for 10 customers, auto-approved |
| Allocation Ratios | Generate Alloc Ratio Test File | Excel file with 50 customers for upload testing |
| Excel Templates | Generate Templates | Blank Excel templates for all upload types (including Interest Rate) |
| FTP / Interest Rates | Generate Rate Data (DB) | 30 days × 3 codes × 4 tenors = 360 approved rows in `ref_interest_rate` |
| FTP / Interest Rates | Seed FTP Product Configs | FTP configs for PROD-LON, PROD-MTG, PROD-DEP, PROD-SAV, PROD-CRD |
| FTP / Interest Rates | Generate Rate Test File | `interest_rate_testdata.xlsx` (360 rows) for upload testing |

**Typical end-to-end setup:**
1. Generate **Master Data** (populates dimension tables)
2. Generate **Instruments** (seeds instrument records ready for allocation and FTP)
3. Generate **Allocations (DB)** (seeds approved allocation ratios)
4. Generate **Rate Data (DB)** (seeds 30 days of approved interest rates)
5. **Seed FTP Product Configs** (configures FTP engine per product)
6. Go to **Batch Execution** → Run Allocation + Run FTP

---

## 27. User Management

**URL:** `/admin/users` (Admin only)

Create, edit, and manage system users.

**Key elements:**
- **User list** — shows username, display name, group memberships, effective permissions, and active status
- **New User** — create a user with username, display name, password, and group assignments
- **Edit User** — change display name, reset password, toggle active status, reassign groups

**How to use:**
1. Click **New User**
2. Enter username, display name, and password
3. Select one or more groups
4. Click **Create User**

---

## 28. Group Management

**URL:** `/admin/groups` (Admin only)

Create and manage permission groups.

**Key elements:**
- **Group list** — shows name, description, permission flags, active status, and member count
- **New Group** — create a group with name, description, and permission checkboxes
- **Edit Group** — modify description, permissions, or active status

**Permission flags:**

| Flag | Effect |
|---|---|
| **Can Make** | Users in this group can create and submit uploads for review |
| **Can Check** | Users in this group can approve or reject uploads (4-Eyes Principle) |
| **Admin** | Users in this group can access `/admin` to manage users and groups |

A user’s effective permissions are the union of all their groups’ permissions.

---

## 29. Starting the Application

**Script:** `start.sh` in the project root

The `start.sh` script handles virtual environment creation, dependency installation, and server startup automatically.

### Commands

```bash
# Development server (default) — auto-creates venv, installs deps, starts Flask with debug
./start.sh
./start.sh dev

# Production daemon — starts Gunicorn in background (4 workers)
./start.sh prod

# Stop Gunicorn daemon
./start.sh stop

# Docker Compose (builds image and starts container)
./start.sh docker
```

### What `start.sh` Does

| Step | dev | prod |
|---|---|---|
| Create venv if missing | ✔ | ✔ |
| Install requirements.txt | ✔ | ✔ |
| Create `instance/` and `uploads/` dirs | ✔ | ✔ |
| Start Flask debug server (foreground) | ✔ | ✕ |
| Start Gunicorn daemon (background) | ✕ | ✔ |

> **Debug mode** is **disabled by default**. Set the `FLASK_DEBUG=1` environment variable only in development. In production, error pages show a friendly message instead of a stack trace.

---

## 30. PWA — Install as Standalone App

BankPFT ships a [Web App Manifest](https://developer.mozilla.org/en-US/docs/Web/Manifest) (`/static/manifest.json`) that enables installation as a standalone Progressive Web App. When launched from the desktop shortcut, the browser frame — including the address bar — is hidden.

**How to install:**

1. Open the app in **Chrome** or **Edge**
2. Look for the **install icon** (desktop icon or "+" symbol) in the address bar, or open the browser menu and select **"Install Management Allocation System"**
3. Click **Install** — a desktop shortcut is created
4. Launch from the shortcut — the app opens full-screen with no browser chrome

**Supported browsers:** Chrome 73+, Edge 79+, Samsung Internet 8.2+. Firefox does not support standalone display mode.

**Manifest settings:**

| Setting | Value |
|---|---|
| Display | `standalone` (no address bar) |
| Theme color | `#1a237e` (dark blue) |
| Start URL | `/` (Dashboard) |
| Icons | 192×192 and 512×512 PNG |
| Start Gunicorn daemon (background) | ✕ | ✔ |
| Write PID to `bankpft.pid` | ✕ | ✔ |
| Write logs to `bankpft.log` | ✕ | ✔ |

### Environment Variables

| Variable | Default | Effect |
|---|---|---|
| `WORKERS` | `4` | Number of Gunicorn worker processes |

**Example — production with 8 workers:**
```bash
WORKERS=8 ./start.sh prod
```

Open http://localhost:5000 after starting in any mode.

---

## End-to-End Workflow Summary

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│   Login      │────>│  Test Data   │────>│  Upload File │────>│   Approve    │────>│  Create Rule │────>│ Run Batch    │
│   (any user) │     │  Generator   │     │  (Maker)     │     │  (Checker)   │     │  (or Import) │     │ Allocation   │
└─────────────┘     └──────────────┘     └──────────────┘     └─────────────┘     └──────────────┘     └──────────────┘
                           │                                                                                      │
                           │ also seeds rate data                                                                 ▼
                           │ + FTP product configs                                                         ┌──────────────┐
                           ▼                                                                               │  View Ledger │
                    ┌──────────────┐     ┌──────────────┐     ┌──────────────┐                            │  Report      │
                    │Upload Interest│───>│ Approve Rates │───>│  Run FTP     │                            └──────────────┘
                    │ Rate File    │     │  (Checker)   │     │  (Batch page)│
                    └──────────────┘     └──────────────┘     └──────────────┘
                                                                      │
                                                                      ▼
                                                               ┌──────────────┐
                                                               │ FTP Run Dtl  │
                                                               │base_rate &   │
                                                               │cost_of_fund  │
                                                               └──────────────┘
```

1. **Start the app** — run `./start.sh` from the project root
2. **Login** as maker1 (or any user with Maker permissions)
3. **Generate** test data — master data, instruments, allocation ratios, interest rates, FTP configs
4. **Upload** files via Data Upload — validation runs automatically
5. **Login** as checker1 (different from the Maker) to approve uploads
6. **Create or import** an allocation rule with optional dimension filters, output mapping, and debit/credit offset
7. **Execute** an allocation batch run to shred balances using the rule
8. **Configure** FTP product configs (or use the seeded defaults from Test Data)
9. **Run FTP** from the Batch Execution page — computes base_rate and cost_of_fund per instrument
10. **Review** allocation results in the Management Ledger Report; FTP results in the FTP Run Detail or via the Table Browser (`proc_inst_data.base_rate`, `proc_inst_data.cost_of_fund`)
