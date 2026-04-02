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
17. [Reports — Index](#17-reports--index)
18. [Management Ledger Report](#18-management-ledger-report)
19. [Operations Report](#19-operations-report)
20. [Database Table Browser](#20-database-table-browser)
21. [Table Browser — Data View](#21-table-browser--data-view)
22. [Test Data Generator](#22-test-data-generator)
23. [User Management](#23-user-management)
24. [Group Management](#24-group-management)
25. [Starting the Application](#25-starting-the-application)

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

---

## 15. Batch Execution

**URL:** `/batch`

Run allocation rules against processed data and view past batch runs.

![Batch Execution](images/06_batch_execution.png)

**How to use:**
1. **Select a Rule** — choose from active allocation rules
2. **As-of Date** — the date to filter source data
3. **Click Run Allocation** — executes the Pandas-based allocation engine

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

Past batch runs are listed below with status, source/output row counts, and links to execution logs.

---

## 16. Batch Execution — Detail

**URL:** `/batch/<batch_id>`

View details of a completed batch run.

![Batch Detail](images/14_batch_detail.png)

**Key elements:**
- Batch metadata (rule used, as-of date, status, timestamps)
- Source and output row counts (output includes both DEBIT and CREDIT entries)
- Orphan count — records with no lookup match
- **Variance** — difference between source total and DEBIT output total (should be 0.00 when ratios sum to 1.0)
- Link to execution log and Management Ledger report

---

## 17. Reports — Index

**URL:** `/reports`

Hub page with links to all available reports.

![Reports Index](images/07_reports_index.png)

**Available reports:**
- **Management Ledger** — aggregated allocation results
- **Operations Report** — system activity summary
- **Database Table Browser** — browse and edit any database table
- **Execution Log** — linked from batch detail pages

---

## 18. Management Ledger Report

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

## 19. Operations Report

**URL:** `/reports/operations`

System activity and health overview.

![Operations Report](images/09_operations.png)

**Key elements:**
- Upload activity by type and status
- Batch execution history
- Record counts across key tables
- System health indicators

---

## 20. Database Table Browser

**URL:** `/reports/tables`

Browse, search, and edit data in any database table.

![Table Browser](images/10_table_browser.png)

**How to use:**
1. **Select a table** from the dropdown
2. **Click Browse** — view the table's data with pagination

All tables are listed, including `fct_mgmt_instrument` for viewing DEBIT/CREDIT entries from allocation runs.

---

## 21. Table Browser — Data View

**URL:** `/reports/tables?table=<table_name>`

View table data with pagination and inline editing.

![Table Data View](images/15_table_browse_data.png)

**Key elements:**
- **Table selector** — switch between tables
- **Column headers** — all columns in the selected table
- **Data rows** — paginated (configurable page size)
- **Edit / Delete** — inline actions for each row
- **Pagination** — navigate through large tables

Useful for verifying dimension data, checking staged records, or inspecting DEBIT/CREDIT allocation entries.

---

## 22. Test Data Generator

**URL:** `/testdata`

Generate realistic test data for the system.

![Test Data Generator](images/11_testdata.png)

**Available generators:**

| Generator | What it creates |
|---|---|
| **Generate Master Data** | Dimension tables: Org Units, Products, Customers, Accounts |
| **Generate Instrument Data** | Sample instrument balances (Excel file) |
| **Generate Allocation Ratios** | Sample allocation ratios (Excel file) |
| **Generate Upload Templates** | Empty Excel templates with correct column headers |
| **Generate Allocation Test Data** | Pre-built allocation test dataset |

**Typical first-time setup:**
1. Click **Generate Master Data** first (populates dimension tables)
2. Click **Generate Instrument Data** (creates an Excel file for upload)
3. Click **Generate Allocation Ratios** (creates ratio data for upload)
4. Go to Data Upload and upload the generated files

---

## 23. User Management

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

## 24. Group Management

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

## 25. Starting the Application

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
                                                                                                                 │
                                                                                                                 ▼
                                                                                                          ┌──────────────┐
                                                                                                          │  View Ledger │
                                                                                                          │  Report      │
                                                                                                          └──────────────┘
```

1. **Start the app** — run `./start.sh` from the project root
2. **Login** as maker1 (or any user with Maker permissions)
3. **Generate** test data (or prepare your own Excel/CSV files)
4. **Upload** files via Data Upload — validation runs automatically
5. **Login** as checker1 (different from the Maker) to approve uploads
6. **Create or import** an allocation rule with optional dimension filters, output mapping, and debit/credit offset
7. **Execute** a batch run to allocate balances using the rule
8. **Review** results in the Management Ledger Report — DEBIT entries show reallocated balances; CREDIT entries confirm the double-entry reversal
