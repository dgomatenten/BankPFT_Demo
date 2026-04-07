# BankPFT — Screen-by-Screen Walkthrough

This guide walks through every screen in the Management Allocation System, explaining what each page does and how to use it.

---

## Table of Contents

1. [Login](#1-login)
2. [Dashboard](#2-dashboard)
3. [Manual Data Load — List](#3-manual-data-load--list)
4. [Manual Data Load — New Upload](#4-manual-data-load--new-upload)
5. [Manual Data Load — Detail & Maker/Checker](#5-manual-data-load--detail--makechecker)
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
18a. [Fund Transfer Pricing — Import Config from JSON](#18a-fund-transfer-pricing--import-config-from-json)
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
31. [Data File Management — Overview](#31-data-file-management--overview)
32. [Data File Management — Batch History](#32-data-file-management--batch-history)
33. [Data File Management — Batch Detail](#33-data-file-management--batch-detail)
34. [REST API — Overview](#34-rest-api--overview)
35. [REST API — Data File Endpoints](#35-rest-api--data-file-endpoints)
36. [REST API — Batch Endpoints](#36-rest-api--batch-endpoints)
37. [Batch Definitions — List](#37-batch-definitions--list)
38. [Batch Definitions — New Definition](#38-batch-definitions--new-definition)
39. [Batch Definitions — Detail & Step Configuration](#39-batch-definitions--detail--step-configuration)
40. [Batch Execution (Redesigned Screen)](#40-batch-execution-redesigned-screen)
41. [Batch Execution — Step-by-Step Detail](#41-batch-execution--step-by-step-detail)
42. [Batch Execution — CUSTOM_SP Step Result](#42-batch-execution--custom_sp-step-result)
43. [SP Run Detail](#43-sp-run-detail)

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

Use the sidebar navigation on the left to reach any module. The **Data Management** group (database icon) expands to show **Manual Data Load** and **Data Files**; it opens automatically when you are on either of those pages. Admin users will see additional **Users**, **Groups**, and **Test Suite** links.

![Sidebar — Data Management group](images/47_sidebar_data_management.png)

---

## 3. Manual Data Load — List

**URL:** `/upload`

Shows all upload batches sorted by date, with their current workflow status. Accessible from the **Data Management** → **Manual Data Load** sidebar menu item.

![Manual Data Load — List](images/48_manual_data_load_list.png)

**Key elements:**
- **File name** — links to the upload detail page
- **Type** — INSTRUMENT, GL, or ALLOCATION
- **Status** — current Maker/Checker workflow state
- **Rows / Errors** — row count and validation error count
- **Maker / Checker** — who uploaded and who approved
- **Delete** — available for DRAFT or REJECTED batches only

Click any file name to view details, or click **New Upload** to upload a file.

---

## 4. Manual Data Load — New Upload

**URL:** `/upload/new`

Upload an Excel (.xlsx) or CSV file for validation and staging.

![New Upload](images/03_upload_new.png)

**How to use:**
1. **Select Data Type** — choose from the dropdown (Instrument Data, General Ledger, Allocation Ratios, Org Reclassification, Static Distribution, Static Allocation). These options are driven by `upload_config.json`
2. **Choose File** — select a `.xlsx` or `.csv` file from your computer
3. **Click Upload & Validate** — the file is parsed, validated against configured rules, and staged. The logged-in user is automatically recorded as the Maker

**Expected Column Headers** — shown at the bottom of the page, generated automatically from the JSON config. Required columns are in bold; optional columns are shown in italics.

After upload, you are redirected to the detail page showing validation results.

---

## 5. Manual Data Load — Detail & Maker/Checker

**URL:** `/upload/<batch_id>`

Shows upload details, validation results, and the Maker/Checker workflow.

![Upload Detail](images/12_upload_detail.png)

**Key elements:**
- **Workflow progress bar** — shows the current state: DRAFT → PENDING → APPROVED → PROCESSED
- **Batch info** — ID, type, status, row count, error count, maker, checker
- **Staged Data Preview** — first 20 rows of the uploaded data
- **Action buttons** (below preview):
  - **Submit for Review** — Maker submits (DRAFT → PENDING)
  - **Approve / Reject** — Checker reviews (PENDING → APPROVED or REJECTED)
- **Post-Approval Action card** — shows the configured post-approval action for this data type. In PENDING state the card reads _"Actions will execute automatically when this batch is approved."_ After approval it displays the execution log table (type, ref, status, detail, timestamp)

![Upload Detail — PENDING with Post-Approval card](images/41_upload_detail_post_approval_pending.png)

![Upload Detail — APPROVED with Post-Approval log](images/42_upload_detail_post_approval_approved.png)

**4-Eyes Rule:** The Checker must be a different user than the Maker, and must belong to a group with the **Can Check** permission. The system enforces both constraints.

### Post-Approval Action Types

Configured per data type in `upload_config.json` under `post_approval`:

| Type | Behaviour | Data types (default) |
|---|---|---|
| `run_rules` | Runs one or more `AllocationRule` IDs (via `rule_ids` list) using `date.today()` as `as_of_date`. Each rule logs SUCCESS / FAILED separately | `INSTRUMENT`, `GL` |
| `stored_procedure` | POC placeholder — logs procedure name with SUCCESS status (no-op until wired to a real SP) | `ALLOCATION`, `DISTRIBUTION` |
| `null` | No post-approval action | `ORG_RECLASS`, `INTEREST_RATE`, `STATIC_ALLOC` |

To configure rule IDs for INSTRUMENT or GL, edit the `rule_ids` array in `upload_config.json`:
```json
"post_approval": {"type": "run_rules", "rule_ids": [4, 5]}
```

---

## 6. Allocation Rules — List

**URL:** `/rules`

Shows all allocation rules with their active/inactive status.

![Rules List](images/04_rules_list.png)

**Key elements:**
- **Rule name** — links to the rule detail page
- **Source / Lookup / Output tables** — the tables this rule operates on
- **Method** — Ratio-Based / Static Distribution / Static Allocation badge
- **Join Key** — the column used to match source data with allocation ratios (blank for Static Allocation)
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
2. **Allocation Method** — choose the method (see below); the Lookup Table and Join Key panels appear/hide based on selection
3. **Distribution Driver** — visible only when **Static Distribution** is selected; enter the `driver_name` that identifies which named driver set within `ref_static_distribution` this rule will use
4. **Source Table** — processed data table to read from
5. **Lookup Table** — allocation ratio table to join with (hidden when Static Allocation is selected)
6. **Output Table** — where to write allocated results (`fct_mgmt_instrument` recommended)
7. **Join Key** — column linking source to lookup (hidden when Static Allocation is selected)
8. **Entry Mode** — choose BOTH, Debit only, or Credit only (see section 8)
9. **Source Dimension Filters** — per-dimension member filter (see section 9)
10. **Debit & Credit Dimension Mapping** — per-dimension output value control (see section 10)
11. **Data Filters** — row-level filter conditions (see section 11)
12. **Click Create Rule** — saved immediately as ACTIVE

All dropdown options are driven by `rule_config.json`.

### Allocation Methods

| Method | Label | How it works | Lookup Table |
|---|---|---|---|
| `RATIO` | Ratio-Based Allocation | Joins source data with a lookup table on the configured join key; splits the balance across target dimensions by ratio. Ratios must sum to 1.0 per join-key group. Unmatched rows are posted as orphans at source org | `ref_static_allocation`, `ref_org_reclass` |
| `DISTRIBUTION` | Static Distribution | Same join-and-ratio logic as RATIO, but uses the dedicated `ref_static_distribution` table. Output dimension value is taken from the `target_dim` column in the distribution table. A **Distribution Driver** must be specified to select which named driver set within the table to use | `ref_static_distribution` |
| `STATIC` | Static Allocation | No lookup join. Each source row maps 1:1 to output at ratio = 1.0. Suitable for aggregation from instrument data or org-level reclassification | `ref_static_alloc` (metadata only, no join) |

> **UI behaviour:** Selecting **Static Allocation** hides the Lookup Table and Join Key controls. Selecting **Static Distribution** pre-selects `ref_static_distribution` as the lookup table and shows the **Distribution Driver** card.

### Distribution Driver

![New Rule — Distribution Driver card](images/39_rule_new_distribution_driver.png)

When **Static Distribution** is selected, a **Distribution Driver** card appears below the Allocation Method card.

| Field | Description |
|---|---|
| **Driver Name** | The `driver_name` value that identifies a named group of rows in `ref_static_distribution`. Must match APPROVED rows in the table (e.g. `PRODUCT_MIX_2026`, `ORG_SPLIT_Q1`) |

**Concept:** `ref_static_distribution` is one physical table that can hold multiple independent distribution sets, each identified by a `driver_name`. Rows for `PRODUCT_MIX_2026` coexist with rows for `ORG_SPLIT_Q1` in the same table. The rule's **Distribution Driver** tells the engine _which_ set to load.

When the engine runs, it queries:
```
SELECT * FROM ref_static_distribution
WHERE status = 'APPROVED'
  AND driver_name = '<rule.distribution_driver>'
```

This means you can maintain multiple versioned or scenario-based distribution drivers without creating separate tables.

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
- **Allocation Method** badge — "Ratio-Based" (blue), "Static Distribution" (green), or "Static Allocation" (cyan)
- **Distribution Driver** — shown below the Allocation Method badge when method is Static Distribution; displays the `driver_name` the rule is bound to (e.g. `PRODUCT_MIX_2026`)
- **Entry Mode** badge — "DEBIT + CREDIT", "DEBIT only", or "CREDIT only"
- **Join Keys** — shows "N/A (Static)" when the Static Allocation method is selected
- **Source Dimension Filters** card — shows mode and members per dimension
- **Debit Entry — Dimension Mapping** card (green) — shows mode and detail per dimension for DEBIT
- **Credit Entry — Dimension Mapping** card (yellow) — shows mode and detail per dimension for CREDIT; shows "same_as_source (default)" if not explicitly configured
- **Data Filters** card — shows saved filter conditions
- **Edit Rule** — opens the edit form with all fields pre-populated
- **Toggle / Delete** actions
- **Allocation ratios preview** — APPROVED ratios the rule would use

![Rule Detail — Distribution Driver](images/40_rule_detail_distribution_driver.png)

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
  "allocation_method": "RATIO",
  "distribution_driver": null,
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

Omitting `credit_dim_json` defaults all credit dimensions to **Same as Source**. Valid `entry_mode` values: `BOTH` (default), `DEBIT_ONLY`, `CREDIT_ONLY`. Valid `allocation_method` values: `RATIO` (default), `DISTRIBUTION`, `STATIC`. When `allocation_method` is `DISTRIBUTION`, set `distribution_driver` to the `driver_name` of the approved driver set to use (e.g. `"distribution_driver": "PRODUCT_MIX_2026"`).

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

The primary interface for running multi-task batch definitions against processed data. Batch definitions group allocation, FTP, data file import/export, and custom stored procedure steps into a single orchestrated run.

![Batch Execution](images/26_batch_execution.png)

The page has three sections:

### Run a Batch (primary action)

1. **Select a Batch Definition** — choose from active multi-task batch definitions
2. **As-of Date** — the calculation date passed to all steps in the batch
3. **Step Preview panel** — dynamically shows the steps in the selected definition as colored badges (Allocation/FTP/Import/Export/Custom SP), the continue-on-error setting, and the description
4. **Execute** — submits the run; the engine executes each step sequentially and redirects to the Execution Detail page

### Batch Definitions table

Lists all active batch definitions with their step types shown as inline colored badges. Use the **Edit** link to open the definition for reconfiguring steps.

### Execution History table

Shows the last 30 batch executions with:
- **Run ID** link → Execution Detail page
- **Batch name** and **as-of date**
- **Status** badge (RUNNING / COMPLETED / FAILED / PARTIAL)
- **Steps** — completed/total count and failed count
- **Run by** and **started** timestamp
- **Duration** in seconds or minutes

### Advanced (collapsible)

A collapsible accordion at the bottom preserves the original individual run panels if you need to trigger a single allocation rule or FTP run directly without a batch definition.

**Create a new batch definition** via the **New Batch Definition** button in the page header (see [Section 38](#38-batch-definitions--new-definition)).

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

## 18a. Fund Transfer Pricing — Import Config from JSON

**URL:** `/ftp/config/import`

Import one or more FTP product configurations from a JSON file or pasted JSON text. This is useful for bulk setup, version control of FTP configurations, or copying configs between environments.

**How to use:**
1. Click **Import JSON** on the FTP Product Config list page (`/ftp/config`)
2. Either **upload a `.json` file** or **paste JSON** into the text area
3. Click **Import Config**

The JSON may be a **single config object** or an **array of config objects**. If a `product_code` already exists in the database, its configuration is updated in-place — no duplicate is created.

**Single config object example:**
```json
{
  "product_code": "LOAN_FIXED",
  "rate_code":    "SWAP_RATE",
  "term": 5,
  "term_mult": "Y",
  "avg_period": 3,
  "avg_period_mult": "M",
  "is_active": true
}
```

**Array example (multiple configs at once):**
```json
[
  {
    "product_code": "LOAN_FIXED",
    "rate_code": "SWAP_RATE",
    "term": 5,
    "term_mult": "Y",
    "avg_period": 3,
    "avg_period_mult": "M"
  },
  {
    "product_code": "DEPOSIT",
    "rate_code": "LIBOR_USD",
    "term": 3,
    "term_mult": "M",
    "avg_period": 1,
    "avg_period_mult": "M"
  }
]
```

**JSON field reference:**

| Field | Required | Default | Notes |
|---|---|---|---|
| `product_code` | Yes | — | Must be unique per config; should match a value in `dim_product` |
| `rate_code` | Yes | — | Must match `interest_rate_code` in the uploaded rate table |
| `term` | Yes | — | Positive integer — the tenor number |
| `term_mult` | No | `M` | `D` (days) / `M` (months, default) / `Y` (years) |
| `avg_period` | No | `1` | Moving-average lookback period length |
| `avg_period_mult` | No | `M` | `D` / `M` (default) / `Y` |
| `method` | No | `MOVING_AVG` | Only `MOVING_AVG` is supported |
| `is_active` | No | `true` | Whether the config is used by the FTP engine |

After a successful import, the UI redirects back to the **FTP Product Config** list page. Flash messages confirm how many configs were imported, updated, or skipped. A reference sample file is provided at `sample_ftp_config.json` in the project root.

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

---

## 31. Data File Management — Overview

**URL:** `/datafile`

Accessible from **Data Management** → **Data Files** in the sidebar.

![Data Files page](images/49_data_files_list.png)

Data File Management provides a JSON-configured batch file I/O engine for loading files from an **inbox** folder and writing output to an **outbox** folder. It operates independently of the Excel upload workflow and does not use the Maker/Checker process.

### File Format Support

| Format | Config key | Field mapping |
|---|---|---|
| Fixed-length | `"type": "fixed_length"` | Slice each field by `start` (byte offset) and `length` |
| Delimited | `"type": "delimited"` | Split by `delimiter`, map by `column` index or `use_header_names: true` |

Common delimiters: `","` (CSV), `"|"` (pipe), `"\t"` (tab), or any single character.

### Per-file Rule JSON

Each import or export is defined in its own JSON file under `app/config/datafile/`. The service scans the directory at startup and registers every file automatically.

**Import rule structure:**
```json
{
  "operation": "import",
  "format_id": "LOAN_FIXED",
  "name": "Loan File — Fixed Length",
  "description": "Fixed-width 120-char loan records.",
  "type": "fixed_length",
  "record_length": 120,
  "target_table": "stg_inst_data",
  "fields": [
    { "name": "account_id",    "start": 0,  "length": 12, "type": "string" },
    { "name": "branch_code",   "start": 12, "length": 4,  "type": "string",
      "transform": "concat('BR', lpad(value, 4, '0'))" },
    { "name": "balance",       "start": 16, "length": 14, "type": "decimal",
      "transform": "to_float(value) / 100" },
    { "name": "maturity_date", "start": 30, "length": 8,  "type": "date",
      "date_format": "YYYYMMDD" }
  ]
}
```

**Export rule structure:**
```json
{
  "operation": "export",
  "export_id": "INST_PROC_EXPORT",
  "name": "Processed Instruments Export",
  "source_table": "proc_inst_data",
  "format": "fixed_length",
  "fields": [
    { "name": "account_id",  "length": 20, "align": "left",  "pad": " " },
    { "name": "balance",     "length": 18, "align": "right", "pad": " " }
  ]
}
```

For delimited exports, set `"format": "delimited"`, `"delimiter": ","`, and optionally `"include_header": true`.

### Transform Expression Sandbox

The `transform` field on an import field is a safe expression evaluated at row load time. The variable `value` holds the raw (stripped) string from the file.

| Category | Available functions / syntax |
|---|---|
| String | `upper(v)`, `lower(v)`, `trim(v)`, `ltrim(v)`, `rtrim(v)`, `left(v,n)`, `right(v,n)`, `substr(v,s,e)`, `lpad(v,n,c)`, `rpad(v,n,c)`, `replace(v,old,new)`, `concat(a,b,...)`, `startswith(v,p)`, `endswith(v,p)`, `contains(v,p)` |
| Conditional | `iif(cond, a, b)`, `a if cond else b`, `nvl(v, default)`, `coalesce(a, b, ...)` |
| Conversion | `to_float(v)`, `to_int(v)` |
| Arithmetic | `+`, `-`, `*`, `/`, `//`, `%`, `**` |
| Slice | `value[0:5]` |

**Examples:**

| Transform expression | Input → Output |
|---|---|
| `concat('BR', lpad(value, 4, '0'))` | `'12'` → `'BR0012'` |
| `to_float(value) / 100` | `'25000000'` → `250000.0` |
| `upper(trim(value))` | `' loan '` → `'LOAN'` |
| `'DEBIT' if to_float(value) > 0 else 'CREDIT'` | `'500'` → `'DEBIT'` |
| `nvl(value, 'UNKNOWN')` | `''` → `'UNKNOWN'` |
| `value[0:8]` | `'20260101extra'` → `'20260101'` |

### Transform Demo Files

Two fully-annotated demo JSON files are provided as copy-paste references:

| File | Purpose |
|---|---|
| `app/config/datafile/import_transform_demo.json` | 10 import transform categories — raw string `value` from file |
| `app/config/datafile/export_transform_demo.json` | 9 export transform categories — Python DB value (str/float/date/None) |

Every field in these files has a `_comment` explaining the transform and showing an input → output example. Copy any field block directly into a production rule JSON.

#### Import Transform Categories

**1. No transform** — value stored as-is after whitespace stripping
```json
{ "name": "account_id", "start": 1, "length": 15, "type": "string" }
```

**2. String case & trim**
```json
{ "name": "product_code", "start": 16, "length": 10, "type": "string",
  "transform": "upper(trim(value))" }
```
`' loan '` → `'LOAN'`

**3. Padding & prefix/suffix**
```json
{ "name": "org_unit_id", "start": 86, "length": 4, "type": "string",
  "transform": "concat('BR', lpad(trim(value), 4, '0'))" }
```
`'12'` → `'BR0012'`

```json
{ "name": "reference_code", "start": 103, "length": 10, "type": "string",
  "transform": "concat('REF-', trim(value), '-2026')" }
```
`'001'` → `'REF-001-2026'`

**4. Substring & slice**
```json
{ "name": "year_part",   "transform": "left(value, 4)" }
{ "name": "month_part",  "transform": "substr(value, 4, 6)" }
{ "name": "last_4_chars","transform": "right(value, 4)" }
{ "name": "slice_syntax","transform": "value[0:8]" }
```
`'20260101'` → `'2026'` / `'01'` / `'0101'` / `'20260101'`

**5. Replace & strip characters**
```json
{ "name": "clean_amount", "transform": "replace(value, ',', '')" }
{ "name": "normalised_id", "transform": "replace(replace(value, '-', ''), ' ', '')" }
```
`'1,234,567'` → `'1234567'` / `'ACC-001 X'` → `'ACC001X'`

**6. Numeric conversion & scaling**
```json
{ "name": "balance",  "type": "float", "transform": "to_float(value) / 100" }
{ "name": "rate_bps", "type": "float", "transform": "to_float(value) / 10000" }
{ "name": "quantity", "type": "float", "transform": "to_int(value)" }
{ "name": "amount_rounded", "transform": "round(to_float(replace(value, ',', '')) / 100, 2)" }
```
`'25000000'` → `250000.0` | `'535'` → `0.0535` | `'1,234,567'` → `12345.67`

**7. Conditional (IF / CASE)**
```json
{ "name": "entry_type", "transform": "'DEBIT' if to_float(value) > 0 else 'CREDIT'" }
{ "name": "entry_type_iif", "transform": "iif(to_float(value) > 0, 'DEBIT', 'CREDIT')" }
{ "name": "risk_bucket",
  "transform": "'HIGH' if to_int(value) >= 80 else ('MED' if to_int(value) >= 50 else 'LOW')" }
{ "name": "in_list_check",
  "transform": "'Y' if upper(trim(value)) in ['LOAN', 'DEPOSIT', 'MTG'] else 'N'" }
```

**8. Null / empty default**
```json
{ "name": "nullable_field", "transform": "nvl(value, 'UNKNOWN')" }
{ "name": "zero_for_blank", "transform": "to_float(nvl(value, '0'))" }
{ "name": "priority_field", "transform": "coalesce(trim(value), 'DEFAULT')" }
```

**9. Date parsing** — use `date_format`, no `transform` needed
```json
{ "name": "as_of_date", "type": "date", "date_format": "%Y%m%d" }   // YYYYMMDD
{ "name": "as_of_date", "type": "date", "date_format": "%d%m%Y" }   // DDMMYYYY
{ "name": "as_of_date", "type": "date", "date_format": "%Y-%m-%d" } // ISO (default)
```

**10. Combined / chained transforms**
```json
{ "name": "normalised_org",
  "transform": "concat('OU-', lpad(replace(trim(value), 'BR', ''), 4, '0'))" }
```
`'BR  7'` → `'OU-0007'`

```json
{ "name": "masked_account",
  "transform": "concat(left(value, 4), '****', right(value, 4))" }
```
`'ACC-12345678'` → `'ACC-****5678'`

---

#### Export Transform Categories

For export fields, `value` is the Python value from the database (may be `str`, `int`, `float`, `date`, or `None`). Use `str(value)` when a string function is needed on a non-string column.

**1. No transform** — written as-is (string pads/truncates to `length`)
```json
{ "source_col": "account_id", "header": "ACCOUNT_ID", "start": 1, "length": 20, "type": "string" }
```

**2. String case**
```json
{ "source_col": "product_code", "transform": "upper(str(value))" }  // 'loan' → 'LOAN'
{ "source_col": "status",       "transform": "lower(str(value))" }  // 'ACTIVE' → 'active'
```

**3. Padding & prefix**
```json
{ "source_col": "org_unit_id", "transform": "lpad(str(value), 10, '0')" }
{ "source_col": "customer_id", "transform": "concat('CUST-', lpad(str(value), 12, '0'))" }
```
`'OU001'` → `'00000OU001'` | `'C001'` → `'CUST-000000000C001'`

**4. Numeric scaling**
```json
{ "source_col": "balance",         "transform": "round(to_float(value) * 100)",  "decimals": 0 }
{ "source_col": "interest_income", "transform": "round(to_float(value) * 10000)","decimals": 0 }
{ "source_col": "balance",                                                         "decimals": 2 }
```
`250000.0` → `25000000` (cents) | `0.0535` → `535` (bps) | `250000.0` → `'250000.00'`

**5. Date reformatting** — use `date_format`
```json
{ "source_col": "as_of_date", "type": "date", "date_format": "%Y-%m-%d" } // 2026-01-01
{ "source_col": "as_of_date", "type": "date", "date_format": "%Y%m%d" }   // 20260101
{ "source_col": "as_of_date", "type": "date", "date_format": "%d%m%Y" }   // 01012026
```

**6. Conditional**
```json
{ "source_col": "balance", "header": "DR_CR_IND",
  "transform": "'DEBIT ' if to_float(value) >= 0 else 'CREDIT'" }
{ "source_col": "balance", "header": "SIGN",
  "transform": "'+' if to_float(value) >= 0 else '-'" }
{ "source_col": "product_code", "header": "PRODUCT_GROUP",
  "transform": "'LENDING' if upper(str(value)) in ['LOAN','MTG','OD'] else ('DEPOSIT' if upper(str(value)) in ['SAV','DEP','TD'] else 'OTHER')" }
```

**7. Null default (NVL)**
```json
{ "source_col": "base_rate",   "transform": "to_float(nvl(value, '0'))", "decimals": 6 }
{ "source_col": "cost_of_fund","transform": "round(to_float(nvl(value, '0')) * 100, 0)", "decimals": 0 }
```
`NULL` → `0.000000` | `NULL` → `0`

**8. Replace & clean**
```json
{ "source_col": "org_unit_id", "transform": "replace(str(value), 'BR', '')" }
{ "source_col": "account_id",  "transform": "replace(replace(str(value), '-', ''), ' ', '')" }
```
`'BR0012'` → `'0012'` | `'ACC-001 X'` → `'ACC001X'`

**9. Combined / chained**
```json
{ "source_col": "balance", "header": "SIGNED_CENTS",
  "transform": "concat('+' if to_float(value) >= 0 else '-', lpad(str(round(abs(to_float(value)) * 100)), 18, '0'))" }
```
`250000.0` → `'+000000000025000000'`

```json
{ "source_col": "balance", "header": "DISPLAY_AMT",
  "transform": "lpad(str(round(to_float(nvl(value, '0')) * 100)), 20, '0')" }
```
Full pipeline: null-safe → scale cents → round → zero-pad to 20 chars.

### Folder Paths

Configured in `app/config/datafile_config.json`:

```json
{
  "global": {
    "inbox_folder":  "uploads/inbox",
    "outbox_folder": "uploads/outbox"
  }
}
```

Place input files in `uploads/inbox/` before triggering an import (via UI or API). Export output files are written to `uploads/outbox/` with a timestamp suffix.

---

## 32. Data File Management — Batch History

**URL:** `/datafile/`

Lists all data file import and export runs in reverse chronological order.

**Columns:**

| Column | Description |
|---|---|
| **ID** | Short UUID (links to detail page) |
| **Operation** | `import` or `export` |
| **Format / Export ID** | The rule ID used (e.g. `LOAN_FIXED`, `INST_PROC_EXPORT`) |
| **File** | Source filename (import) or generated output filename (export) |
| **Target / Source Table** | Database table read from or written to |
| **Status** | `RUNNING`, `COMPLETED`, or `FAILED` |
| **Rows** | Number of rows processed |
| **Errors** | Number of row-level errors |
| **Run By** | Username who triggered the run |
| **Completed** | Timestamp |

Click any batch ID to view full details and per-row errors.

---

## 33. Data File Management — Batch Detail

**URL:** `/datafile/<batch_id>`

Full detail page for a single import or export run.

**Key sections:**

- **Summary card** — operation, format/export ID, status, filename, target table, row count, error count, run by, started/completed timestamps, and error message (if failed)
- **Row Errors** — table of per-row errors with row number, field name, raw value, and error description. Shown only when `error_count > 0`

Errors do not stop the import — rows with errors are skipped and the remaining rows are loaded. The batch status is `COMPLETED` unless a fatal error occurs.

---

## 34. REST API — Overview

**Base URL:** `/api/v1/`

All API endpoints use **HTTP Basic Auth** with existing user credentials. No session cookies or tokens are required. All request bodies and responses are JSON.

### Authentication

Add an `Authorization` header to every request:

```bash
curl -u admin:admin http://localhost:5000/api/v1/datafile/formats
```

Or construct the header manually:

```
Authorization: Basic <base64(username:password)>
```

**401 response** (invalid or missing credentials):
```json
{"error": "Unauthorized — provide valid credentials via HTTP Basic Auth"}
```

The response also includes a `WWW-Authenticate: Basic realm="BankPFT API"` header.

### HTTP Status Codes

| Code | Meaning |
|---|---|
| `200` | Success |
| `400` | Bad request — missing or invalid body field |
| `401` | Unauthorized — invalid or missing credentials |
| `404` | Resource not found |
| `422` | Run triggered but completed with errors (check `error_message` / `errors` field) |

### Available Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/datafile/formats` | List available import format IDs |
| `GET` | `/api/v1/datafile/exports` | List available export config IDs |
| `POST` | `/api/v1/datafile/import` | Trigger a file import |
| `POST` | `/api/v1/datafile/export` | Trigger a file export |
| `GET` | `/api/v1/datafile/batch/<id>` | Get import/export batch status |
| `GET` | `/api/v1/batch/rules` | List active allocation rules |
| `POST` | `/api/v1/rules/import` | Import an allocation rule from JSON body |
| `POST` | `/api/v1/batch/allocation` | Run an allocation batch |
| `GET` | `/api/v1/batch/allocation/<id>` | Get allocation batch status |
| `POST` | `/api/v1/batch/ftp` | Run the FTP calculation engine |
| `GET` | `/api/v1/batch/ftp/<id>` | Get FTP run status |
| `GET` | `/api/v1/ftp/configs` | List all FTP product configurations |
| `POST` | `/api/v1/ftp/config/import` | Import one or more FTP product configs from JSON |

---

## 35. REST API — Data File Endpoints

### GET `/api/v1/datafile/formats`

Returns all registered import format definitions.

```bash
curl -u admin:admin http://localhost:5000/api/v1/datafile/formats
```

**Response — real format IDs available in this system:**
```json
{
  "formats": [
    { "format_id": "LOAN_FIXED",  "name": "Loan Data — Fixed Length",                     "type": "fixed_length", "target_table": "stg_inst_data" },
    { "format_id": "INST_FIXED",  "name": "Instrument Data — Fixed Length",               "type": "fixed_length", "target_table": "stg_inst_data" },
    { "format_id": "INST_CSV",    "name": "Instrument Data — CSV (Comma Delimited)",      "type": "delimited",    "target_table": "stg_inst_data" },
    { "format_id": "GL_FIXED",    "name": "GL Data — Fixed Length",                       "type": "fixed_length", "target_table": "stg_gl_data" },
    { "format_id": "GL_PIPE",     "name": "GL Data — Pipe Delimited (header-mapped)",     "type": "delimited",    "target_table": "stg_gl_data" }
  ]
}
```

---

### GET `/api/v1/datafile/exports`

Returns all registered export configurations.

```bash
curl -u admin:admin http://localhost:5000/api/v1/datafile/exports
```

**Response — real export IDs available in this system:**
```json
{
  "exports": [
    { "export_id": "INST_PROC_EXPORT",   "name": "Processed Instruments Export",         "format": "fixed_length", "source_table": "proc_inst_data" },
    { "export_id": "INST_CSV_EXPORT",    "name": "Processed Instruments Export — CSV",   "format": "delimited",    "source_table": "proc_inst_data" },
    { "export_id": "ALLOC_RESULT_EXPORT","name": "Allocation Results Export",             "format": "fixed_length", "source_table": "fct_mgmt_ledger" }
  ]
}
```

---

### POST `/api/v1/datafile/import`

Triggers a data file import. The file must already exist in the configured inbox folder (`uploads/inbox/`).

| Field | Required | Description |
|---|---|---|
| `format_id` | Yes | Must match a registered import rule (see formats list above) |
| `filename` | Yes | Filename only — no path, no `..`. File must exist in the inbox folder |

#### Example calls for each format

**Fixed-length loan file (`LOAN_FIXED`)**
```bash
curl -u admin:admin \
     -X POST \
     -H 'Content-Type: application/json' \
     -d '{"format_id": "LOAN_FIXED", "filename": "loan.dat"}' \
     http://localhost:5000/api/v1/datafile/import
```

**Fixed-length instrument file (`INST_FIXED`)**
```bash
curl -u admin:admin \
     -X POST \
     -H 'Content-Type: application/json' \
     -d '{"format_id": "INST_FIXED", "filename": "instruments_20260101.dat"}' \
     http://localhost:5000/api/v1/datafile/import
```

**CSV instrument file (`INST_CSV`)**
```bash
curl -u admin:admin \
     -X POST \
     -H 'Content-Type: application/json' \
     -d '{"format_id": "INST_CSV", "filename": "instruments_20260101.csv"}' \
     http://localhost:5000/api/v1/datafile/import
```

**Fixed-length GL file (`GL_FIXED`)**
```bash
curl -u admin:admin \
     -X POST \
     -H 'Content-Type: application/json' \
     -d '{"format_id": "GL_FIXED", "filename": "gl_20260101.dat"}' \
     http://localhost:5000/api/v1/datafile/import
```

**Pipe-delimited GL file with header names (`GL_PIPE`)**
```bash
curl -u admin:admin \
     -X POST \
     -H 'Content-Type: application/json' \
     -d '{"format_id": "GL_PIPE", "filename": "gl_20260101.txt"}' \
     http://localhost:5000/api/v1/datafile/import
```

**Python equivalent**
```python
import requests

BASE = "http://localhost:5000"
AUTH = ("admin", "admin")

# Import a fixed-length loan file
r = requests.post(
    f"{BASE}/api/v1/datafile/import",
    json={"format_id": "LOAN_FIXED", "filename": "loan.dat"},
    auth=AUTH
)
print(r.status_code, r.json())

# Import a CSV instrument file
r = requests.post(
    f"{BASE}/api/v1/datafile/import",
    json={"format_id": "INST_CSV", "filename": "instruments_20260101.csv"},
    auth=AUTH
)
print(r.status_code, r.json())
```

**Success response (`200`):**
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
  "started_at": "2026-01-01T09:00:00Z",
  "completed_at": "2026-01-01T09:00:01Z"
}
```

**Partial success with row errors (`422`):** Rows with parse errors are skipped; valid rows are still loaded.
```json
{
  "batch_id": "...",
  "status": "COMPLETED",
  "row_count": 10,
  "error_count": 2,
  "errors": [
    { "row": 3, "field": "balance",  "raw_value": "INVALID", "error": "cannot convert to float" },
    { "row": 7, "field": "as_of_date","raw_value": "99999999","error": "date parse failed" }
  ]
}
```

**Bad request (`400`) — missing or invalid field:**
```json
{ "error": "format_id is required" }
{ "error": "filename is invalid or missing" }
```

---

### POST `/api/v1/datafile/export`

Triggers a data file export. Output is written to `uploads/outbox/` with a timestamp in the filename.

| Field | Required | Description |
|---|---|---|
| `export_id` | Yes | Must match a registered export rule (see exports list above) |
| `as_of_date` | No | `YYYY-MM-DD` — filter source rows by date. Defaults to today |

#### Example calls for each export

**Fixed-length processed instruments export (`INST_PROC_EXPORT`)**
```bash
curl -u admin:admin \
     -X POST \
     -H 'Content-Type: application/json' \
     -d '{"export_id": "INST_PROC_EXPORT", "as_of_date": "2026-01-01"}' \
     http://localhost:5000/api/v1/datafile/export
```

**CSV instruments export (`INST_CSV_EXPORT`)**
```bash
curl -u admin:admin \
     -X POST \
     -H 'Content-Type: application/json' \
     -d '{"export_id": "INST_CSV_EXPORT", "as_of_date": "2026-01-01"}' \
     http://localhost:5000/api/v1/datafile/export
```

**Allocation results export (DEBIT entries only, `ALLOC_RESULT_EXPORT`)**
```bash
curl -u admin:admin \
     -X POST \
     -H 'Content-Type: application/json' \
     -d '{"export_id": "ALLOC_RESULT_EXPORT", "as_of_date": "2026-01-01"}' \
     http://localhost:5000/api/v1/datafile/export
```

**Omit `as_of_date` to default to today**
```bash
curl -u admin:admin \
     -X POST \
     -H 'Content-Type: application/json' \
     -d '{"export_id": "INST_PROC_EXPORT"}' \
     http://localhost:5000/api/v1/datafile/export
```

**Python equivalent**
```python
import requests

BASE = "http://localhost:5000"
AUTH = ("admin", "admin")

# Export fixed-length instruments for a specific date
r = requests.post(
    f"{BASE}/api/v1/datafile/export",
    json={"export_id": "INST_PROC_EXPORT", "as_of_date": "2026-01-01"},
    auth=AUTH
)
result = r.json()
print(result["status"], "rows:", result["row_count"], "file:", result["filename"])

# Export CSV instruments (no date filter — all rows)
r = requests.post(
    f"{BASE}/api/v1/datafile/export",
    json={"export_id": "INST_CSV_EXPORT"},
    auth=AUTH
)
print(r.json())
```

**Success response (`200`):**
```json
{
  "batch_id": "8f1e1f89-62d0-4baa-b6d9-39a74eae20f3",
  "operation": "export",
  "format_id": "INST_PROC_EXPORT",
  "format_name": "Processed Instruments Export",
  "filename": "INST_PROC_EXPORT_20260101_090000.dat",
  "status": "COMPLETED",
  "row_count": 55,
  "error_count": 0,
  "errors": [],
  "error_message": null,
  "run_by": "admin",
  "started_at": "2026-01-01T09:00:00Z",
  "completed_at": "2026-01-01T09:00:01Z"
}
```

**Bad request (`400`) — missing export_id:**
```json
{ "error": "export_id is required" }
```

---

### GET `/api/v1/datafile/batch/<batch_id>`

Poll the status of any import or export batch using the `batch_id` from the trigger response.

```bash
# Replace the UUID with the batch_id returned by the import or export call
curl -u admin:admin \
     http://localhost:5000/api/v1/datafile/batch/21ef93cb-b7af-4073-8c2f-8417b2a40f8d
```

**Python — trigger and poll pattern**
```python
import requests, time

BASE = "http://localhost:5000"
AUTH = ("admin", "admin")

# 1. Trigger the import
r = requests.post(
    f"{BASE}/api/v1/datafile/import",
    json={"format_id": "INST_FIXED", "filename": "instruments_20260101.dat"},
    auth=AUTH
)
batch_id = r.json()["batch_id"]

# 2. Poll until done (runs synchronously, but pattern works for long batches too)
while True:
    status = requests.get(f"{BASE}/api/v1/datafile/batch/{batch_id}", auth=AUTH).json()
    print(status["status"], "rows:", status["row_count"], "errors:", status["error_count"])
    if status["status"] in ("COMPLETED", "FAILED"):
        break
    time.sleep(1)

# 3. Check for row-level errors
if status["error_count"] > 0:
    for err in status["errors"]:
        print(f"  Row {err['row']} | {err['field']} = '{err['raw_value']}' → {err['error']}")
```

Response shape is identical to the `POST /import` or `POST /export` response.

---

## 36. REST API — Batch Endpoints

### GET `/api/v1/batch/rules`

Returns all active allocation rules.

**Response:**
```json
{
  "rules": [
    {
      "rule_id": 1,
      "name": "Customer Shred — Static Alloc",
      "description": "Shred instrument balances by customer ratio.",
      "source_table": "proc_inst_data",
      "lookup_table": "ref_static_allocation",
      "output_table": "fct_mgmt_instrument"
    }
  ]
}
```

---

### POST `/api/v1/batch/allocation`

Runs an allocation batch synchronously and returns the result.

**Request body:**
```json
{ "rule_id": 1, "as_of_date": "2026-01-01" }
```

| Field | Required | Description |
|---|---|---|
| `rule_id` | Yes | Integer ID of an active allocation rule |
| `as_of_date` | No | `YYYY-MM-DD` — defaults to today |

**Success response (`200`):**
```json
{
  "batch_id": "a1b2c3d4-...",
  "rule_id": 1,
  "as_of_date": "2026-01-01",
  "status": "COMPLETED",
  "source_row_count": 120,
  "output_row_count": 240,
  "orphan_count": 0,
  "source_total": 5000000.0,
  "output_total": 5000000.0,
  "run_by": "admin",
  "error_message": null,
  "started_at": "2026-01-01T09:00:00Z",
  "completed_at": "2026-01-01T09:00:02Z"
}
```

**If the rule is not found or inactive → `404`:**
```json
{ "error": "rule_id 99 not found or inactive" }
```

---

### GET `/api/v1/batch/allocation/<batch_id>`

Returns the status of a previously triggered allocation batch. Same response shape as `POST /batch/allocation`.

---

### POST `/api/v1/batch/ftp`

Runs the FTP moving-average engine for a given as-of date.

**Request body:**
```json
{ "as_of_date": "2026-01-01" }
```

| Field | Required | Description |
|---|---|---|
| `as_of_date` | No | `YYYY-MM-DD` — defaults to today |

**Success response (`200`):**
```json
{
  "run_id": "f0a1b2c3-...",
  "as_of_date": "2026-01-01",
  "status": "COMPLETED",
  "instruments_processed": 500,
  "instruments_matched": 480,
  "instruments_skipped": 20,
  "run_by": "admin",
  "error_message": null,
  "started_at": "2026-01-01T09:00:00Z",
  "completed_at": "2026-01-01T09:00:03Z"
}
```

---

### GET `/api/v1/batch/ftp/<run_id>`

Returns the status of a previously triggered FTP run. Same response shape as `POST /batch/ftp`.

---

### POST `/api/v1/rules/import`

Imports an allocation rule directly from a JSON body. Equivalent to using the `/rules/import` web UI but accessible programmatically. The rule is created immediately as `ACTIVE`.

**Request body** — same schema as the `/rules/import` web form:

| Field | Required | Default | Notes |
|---|---|---|---|
| `name` | **Yes** | — | Display name |
| `description` | No | `""` | Free-text notes |
| `source_table` | No | `proc_inst_data` | Source data table |
| `lookup_table` | No | `ref_static_allocation` | Ratio lookup table |
| `output_table` | No | `fct_mgmt_instrument` | Output destination |
| `join_key` | No | `customer_id` | Column linking source ↔ lookup |
| `entry_mode` | No | `BOTH` | `BOTH` / `DEBIT_ONLY` / `CREDIT_ONLY` |
| `filter_json` | No | — | Row-level filter object |
| `source_dim_json` | No | — | Per-dimension source member filter |
| `output_dim_json` | No | — | Per-dimension DEBIT dimension mapping |
| `credit_dim_json` | No | — | Per-dimension CREDIT dimension mapping |

**curl example:**
```bash
curl -u admin:admin \
     -X POST \
     -H 'Content-Type: application/json' \
     -d '{
       "name": "Customer Shred Q2",
       "source_table": "proc_inst_data",
       "lookup_table": "ref_static_allocation",
       "output_table": "fct_mgmt_instrument",
       "join_key": "customer_id",
       "entry_mode": "BOTH"
     }' \
     http://localhost:5000/api/v1/rules/import
```

**Success response (`201 Created`):**
```json
{
  "rule_id": 5,
  "name": "Customer Shred Q2",
  "status": "ACTIVE",
  "entry_mode": "BOTH",
  "created_by": "admin",
  "created_at": "2026-04-04T00:00:00Z"
}
```

**Error (`400`) — missing name:**
```json
{ "error": "JSON must contain a 'name' field" }
```

---

### GET `/api/v1/ftp/configs`

Returns all FTP product configurations (active and inactive).

**curl example:**
```bash
curl -u admin:admin http://localhost:5000/api/v1/ftp/configs
```

**Response:**
```json
{
  "configs": [
    {
      "id": 1,
      "product_code": "PROD-LON",
      "method": "MOVING_AVG",
      "rate_code": "SWAP_RATE",
      "term": 5,
      "term_mult": "Y",
      "avg_period": 3,
      "avg_period_mult": "M",
      "is_active": true,
      "created_by": "system"
    }
  ]
}
```

---

### POST `/api/v1/ftp/config/import`

Imports one or more FTP product configurations from a JSON body. If a `product_code` already exists, its configuration is updated in-place (no duplicate created).

The body may be a **single object** or an **array of objects**.

| Field | Required | Default | Notes |
|---|---|---|---|
| `product_code` | **Yes** | — | Must match `dim_product`; unique key |
| `rate_code` | **Yes** | — | Must match `interest_rate_code` in rate table |
| `term` | **Yes** | — | Positive integer tenor number |
| `term_mult` | No | `M` | `D` / `M` / `Y` |
| `avg_period` | No | `1` | Moving-average lookback period |
| `avg_period_mult` | No | `M` | `D` / `M` / `Y` |
| `method` | No | `MOVING_AVG` | Only `MOVING_AVG` is supported |
| `is_active` | No | `true` | Whether config is used by FTP engine |

**curl — array of configs:**
```bash
curl -u admin:admin \
     -X POST \
     -H 'Content-Type: application/json' \
     -d '[
       {"product_code": "LOAN_FIXED", "rate_code": "SWAP_RATE", "term": 5, "term_mult": "Y", "avg_period": 3, "avg_period_mult": "M"},
       {"product_code": "DEPOSIT",    "rate_code": "LIBOR_USD",  "term": 3, "term_mult": "M"}
     ]' \
     http://localhost:5000/api/v1/ftp/config/import
```

**curl — single config:**
```bash
curl -u admin:admin \
     -X POST \
     -H 'Content-Type: application/json' \
     -d '{"product_code": "CREDIT_CARD", "rate_code": "PRIME_RATE", "term": 1, "term_mult": "Y"}' \
     http://localhost:5000/api/v1/ftp/config/import
```

**Success response (`200`):**
```json
{ "imported": 2, "updated": 0, "skipped": 0, "errors": [] }
```

**Partial success with validation errors (`422` when all items are skipped):**
```json
{
  "imported": 1,
  "updated": 0,
  "skipped": 1,
  "errors": ["Item 2 ('BAD_CODE'): missing 'rate_code' — skipped"]
}
```

**Python example (import a config file from disk):**
```python
import json, requests

BASE = "http://localhost:5000"
AUTH = ("admin", "admin")

with open("sample_ftp_config.json") as f:
    configs = json.load(f)

r = requests.post(f"{BASE}/api/v1/ftp/config/import", json=configs, auth=AUTH)
result = r.json()
print(f"Imported: {result['imported']}, Updated: {result['updated']}, Skipped: {result['skipped']}")
if result["errors"]:
    for err in result["errors"]:
        print(" Error:", err)
```

---

### GET `/api/v1/batch/definitions`

Returns all active multi-task batch definitions with step counts.

**Response:**
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

---

### GET `/api/v1/batch/definitions/<def_id>`

Returns a single batch definition including its full ordered step list.

**Response:**
```json
{
  "definition_id": 1,
  "name": "Month-End Close",
  "continue_on_error": false,
  "step_count": 4,
  "steps": [
    { "step_order": 1, "task_type": "DATAFILE_IMPORT", "ref_id": "LOAN_FIXED",          "label": "Import loan file" },
    { "step_order": 2, "task_type": "ALLOCATION",      "ref_id": "1",                   "label": "Shred inst balances" },
    { "step_order": 3, "task_type": "FTP",             "ref_id": null,                  "label": "FTP calculation" },
    { "step_order": 4, "task_type": "DATAFILE_EXPORT", "ref_id": "ALLOC_RESULT_EXPORT", "label": "Export results" }
  ]
}
```

---

### POST `/api/v1/batch/definitions/<def_id>/run`

Executes a batch definition synchronously. All steps run in order; on failure the behaviour depends on `continue_on_error`.

**Request body:**
```json
{ "as_of_date": "2026-01-31" }
```

| Field | Required | Description |
|---|---|---|
| `as_of_date` | No | `YYYY-MM-DD` — defaults to today |

**Success response (`200` when all steps complete, `422` when one or more steps fail):**
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

**Overall `status` values:**

| Value | Meaning |
|---|---|
| `RUNNING` | Currently in progress |
| `COMPLETED` | All steps finished successfully |
| `FAILED` | First step failed and `continue_on_error=false` |
| `PARTIAL` | One or more steps failed; `continue_on_error=true` allowed remaining steps to run |

**Step `status` values:** `PENDING` → `RUNNING` → `COMPLETED` / `FAILED` / `SKIPPED`

---

### GET `/api/v1/batch/executions/<exec_id>`

Polls the status of a multi-task batch execution. Returns the same response shape as `POST /batch/definitions/<id>/run`.

---

### curl Quick Reference

```bash
BASE=http://localhost:5000
AUTH="-u admin:admin"

# List available import formats
curl $AUTH $BASE/api/v1/datafile/formats

# Trigger a file import
curl $AUTH -X POST -H 'Content-Type: application/json' \
  -d '{"format_id":"LOAN_FIXED","filename":"loan.dat"}' \
  $BASE/api/v1/datafile/import

# Trigger a file export
curl $AUTH -X POST -H 'Content-Type: application/json' \
  -d '{"export_id":"INST_PROC_EXPORT","as_of_date":"2026-01-01"}' \
  $BASE/api/v1/datafile/export

# List active allocation rules
curl $AUTH $BASE/api/v1/batch/rules

# Run an allocation batch
curl $AUTH -X POST -H 'Content-Type: application/json' \
  -d '{"rule_id":1,"as_of_date":"2026-01-01"}' \
  $BASE/api/v1/batch/allocation

# Run FTP
curl $AUTH -X POST -H 'Content-Type: application/json' \
  -d '{"as_of_date":"2026-01-01"}' \
  $BASE/api/v1/batch/ftp

# List active multi-task batch definitions
curl $AUTH $BASE/api/v1/batch/definitions

# Get definition 1 with its step list
curl $AUTH $BASE/api/v1/batch/definitions/1

# Execute definition 1 for 2026-01-31
curl $AUTH -X POST -H 'Content-Type: application/json' \
  -d '{"as_of_date":"2026-01-31"}' \
  $BASE/api/v1/batch/definitions/1/run

# Poll status
curl $AUTH $BASE/api/v1/datafile/batch/<batch_id>
curl $AUTH $BASE/api/v1/batch/allocation/<batch_id>
curl $AUTH $BASE/api/v1/batch/ftp/<run_id>
curl $AUTH $BASE/api/v1/batch/executions/<execution_id>
```

---

## 37. Batch Definitions — List

**URL:** `/batch/definitions`

Manage all multi-task batch definitions. A batch definition is a named, ordered sequence of steps (allocation rules, FTP runs, data file imports/exports, and custom stored procedures) that are executed together in a single orchestrated run.

![Batch Definitions List](images/27_batch_definitions.png)

**Table columns:**

| Column | Description |
|---|---|
| **Name** | Clickable link to the definition detail/configuration page |
| **Description** | Optional free-text description |
| **Steps** | Number of task steps configured |
| **On Error** | `Stop` (default) or `Continue` — controls whether remaining steps run after a failure |
| **Active** | Green check = active, visible on the Batch Execution screen |
| **Actions** | Edit / Delete |

**Buttons:**
- **New Batch Definition** — opens the creation form (see [Section 38](#38-batch-definitions--new-definition))
- Each definition name links to its **Detail** page where steps are managed (see [Section 39](#39-batch-definitions--detail--step-configuration))

---

## 38. Batch Definitions — New Definition

**URL:** `/batch/definitions/new`

Create a new multi-task batch definition.

![New Batch Definition](images/28_batch_def_new.png)

**Fields:**

| Field | Description |
|---|---|
| **Name** | Unique display name for this batch |
| **Description** | Optional description shown in the step preview and history |
| **Continue on Error** | If checked, subsequent steps run even when an earlier step fails; default is to stop on first failure |

After saving, you are taken to the **Definition Detail** page to add and order steps.

---

## 39. Batch Definitions — Detail & Step Configuration

**URL:** `/batch/definitions/<id>`

Configure the ordered steps of a batch definition and run it.

![Batch Definition Detail](images/29_batch_def_detail.png)

### Left panel — Step list

Shows all configured steps in execution order. Each row shows:
- **Step #** — execution sequence number
- **Type badge** — color-coded: primary=ALLOCATION, info=FTP, success=DATAFILE\_IMPORT, warning=DATAFILE\_EXPORT, secondary=CUSTOM\_SP
- **Ref ID** — the allocation rule ID, data file format name, or SP name for this step
- **Label** — human-readable step name
- **Remove** — removes this step from the definition

### Add Step form

| Field | Description |
|---|---|
| **Task Type** | ALLOCATION / FTP / DATAFILE\_IMPORT / DATAFILE\_EXPORT / CUSTOM\_SP |
| **Ref** | Dynamic field — shows a rule dropdown for ALLOCATION, a format select for import/export, or a text field for CUSTOM\_SP. Hidden for FTP (no ref needed) |
| **Label** | Auto-filled from the type+ref when left blank; override as needed |

New steps are appended at the end and assigned the next step order number.

### CUSTOM_SP Step

When **CUSTOM_SP** is selected as the Task Type, two additional fields appear:

![CUSTOM_SP form](images/44_batch_def_custom_sp_form.png)

| Field | Description |
|---|---|
| **SP Name** | Stored procedure name. An optional `schema.` prefix is allowed (e.g. `reporting.sp_month_end_alloc`). The name is validated against a strict identifier pattern — spaces, hyphens, semicolons, and SQL injection sequences are rejected |
| **Parameters** | Optional JSON object. Keys become named bind parameters passed to `CALL sp_name(:key, ...)`. Runtime tokens `{as_of_date}` and `{run_by}` are resolved at dispatch time |

**Runtime token reference:**

| Token | Resolved to | Example |
|---|---|---|
| `{as_of_date}` | Batch as-of date (ISO string) | `"2026-04-30"` |
| `{run_by}` | Username who triggered the batch | `"admin"` |

**Example params JSON:**
```json
{"p_as_of_date": "{as_of_date}", "p_run_by": "{run_by}"}
```
Resolved at runtime to: `CALL reporting.sp_month_end_alloc(:p_as_of_date, :p_run_by)` with values bound via SQLAlchemy named parameters.

**Execution behavior:** The SP is executed **synchronously** — the batch waits for the SP to complete before moving to the next step. The step status becomes **COMPLETED** or **FAILED**, exactly like any other step type. The Run ID link in the execution step table opens the SP Run Detail page to view timing, resolved parameters, and any error messages.

### Right panel — Run This Batch

- **As-of Date** — the calculation date for all steps
- **Execute** — triggers the batch run and redirects to the **Execution Detail** page
- **Recent executions** — a compact table of the last 5 runs for this definition with status and duration

---

## 40. Batch Execution (Redesigned Screen)

**URL:** `/batch`

Once one or more batch definitions exist, the Batch Execution screen shows definitions and their execution history prominently.

![Batch Execution with History](images/30_batch_def_run.png)

The **Step Preview** panel on the right side of the Run card dynamically populates when you select a definition:
- Colored step badges (one per task step)
- **On Error** badge — Stop or Continue
- Description text

This lets you confirm the right definition is selected before executing.

---

## 41. Batch Execution — Step-by-Step Detail

**URL:** `/batch/executions/<execution_id>`

View the granular results of a multi-task batch execution, including per-step status and links to each step's underlying run record.

![Batch Execution Step Detail](images/31_batch_execution_detail.png)

### Summary cards

| Card | Description |
|---|---|
| **Started** | Timestamp when the batch began |
| **Completed** | Timestamp when all steps finished (or the run failed) |
| **Total Steps** | Number of steps in the definition at execution time |
| **Failed / Skipped** | Count of steps that failed or were skipped due to a prior failure |

### Step results table

| Column | Description |
|---|---|
| **Step #** | Execution order |
| **Type** | Color-coded task type badge |
| **Label** | The step's display label |
| **Status** | PENDING / RUNNING / COMPLETED / FAILED / SKIPPED |
| **Summary / Error** | Engine summary (row counts, variance) or error message |
| **Started / Ended** | Per-step timestamps |
| **Run ID** | Deep link to the underlying engine run — allocation BatchRun detail, FTP run detail, or DataFile batch detail |

**Status badge colors:**
- `COMPLETED` → green
- `FAILED` → red
- `SKIPPED` → secondary (grey)
- `RUNNING` → blue
- `PENDING` → light

**Navigation**: use the breadcrumb or **Back to Batch Execution** link to return to the main `/batch` screen.

---

## 42. Batch Execution — CUSTOM_SP Step Result

**URL:** `/batch/executions/<execution_id>`

When a batch includes a `CUSTOM_SP` step, that step executes **synchronously** — the batch waits for the stored procedure to finish before moving to the next step.

**CUSTOM_SP step indicators in the step results table:**
- **Status badge:** Green `COMPLETED` badge (or red `FAILED` if the SP raised an error)
- **Run ID link:** The Run ID cell contains a link directly to the SP Run detail page (`/batch/sp-runs/<run_id>`)
- `completed_at` is set when the SP returns, just like any other step type

The overall execution status reflects the actual SP outcome. If the SP fails and `continue_on_error` is false, the execution is marked `FAILED` and remaining steps are skipped.

---

## 43. SP Run Detail

**URL:** `/batch/sp-runs/<run_id>`

View timing, parameters, and result for a single SP run. Access via the Run ID link on the batch execution detail step row.

![SP Run Detail — Completed](images/45_sp_detail_completed.png)

### Timing cards

| Card | Description |
|---|---|
| **Started** | Timestamp when `run_sp()` created the SpRun record |
| **Completed** | Timestamp when the SP returned (always set — SP runs synchronously) |
| **Duration** | Elapsed time in seconds |
| **Run By** | Username who triggered the batch |

### Parameters panel

Shows the key/value pairs **after token resolution** — the actual values passed to the stored procedure:

| Example key | Example value | Source |
|---|---|---|
| `p_as_of_date` | `2026-04-06` | Resolved from `{as_of_date}` token |
| `p_run_by` | `admin` | Resolved from `{run_by}` token |

If no parameters were configured, the panel shows "No parameters".

### Result / Error panel

| Status | Panel content |
|---|---|
| **COMPLETED** | "Stored procedure executed successfully." |
| **FAILED** | PostgreSQL/database exception message (e.g. `ERROR: routine "sp_does_not_exist" does not exist`) |

![SP Run Detail — Failed](images/46_sp_detail_failed.png)

**Navigation:** Use the ← back arrow button to return to the parent batch execution detail page.

