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
8. [Allocation Rules — Data Filter Editor](#8-allocation-rules--data-filter-editor)
9. [Allocation Rules — Detail (with Filters)](#9-allocation-rules--detail-with-filters)
10. [Batch Execution](#10-batch-execution)
11. [Batch Execution — Detail](#11-batch-execution--detail)
12. [Reports — Index](#12-reports--index)
13. [Management Ledger Report](#13-management-ledger-report)
14. [Operations Report](#14-operations-report)
15. [Database Table Browser](#15-database-table-browser)
16. [Table Browser — Data View](#16-table-browser--data-view)
17. [Test Data Generator](#17-test-data-generator)
18. [User Management](#18-user-management)
19. [Group Management](#19-group-management)

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
- **Toggle / Delete** — activate/deactivate or remove a rule

Rules are immediately active when created (no Maker/Checker workflow for rules).

---

## 7. Allocation Rules — New Rule

**URL:** `/rules/new`

Create a new allocation rule by configuring its source-to-output mapping.

![New Rule](images/05_rules_new.png)

**How to use:**
1. **Rule Name** — give the rule a descriptive name (e.g., "Customer Shred Q1")
2. **Description** — optional notes about the rule's purpose
3. **Source Table** — the processed data table to read from (dropdown options from `rule_config.json`)
4. **Lookup Table** — the allocation ratio table to join with
5. **Output Table** — where to write the allocated results
6. **Join Key** — the column used to join source data with ratios (e.g., customer_id, org_unit_id, product_code)
7. **Data Filters** — optional conditions to filter source data before allocation (see next section)
8. **Click Create Rule** — the rule is saved and immediately active. The logged-in user is automatically recorded as the creator

All dropdown options are driven by `rule_config.json` — add new tables or join keys by editing the config file.

---

## 8. Allocation Rules — Data Filter Editor

**URL:** `/rules/new` (bottom of the form)

The filter editor lets you restrict which source rows are included when the allocation engine runs.

![Filter Editor with Conditions](images/17_rule_filter_conditions.png)

**How to use:**
1. **Click "Add Condition"** — adds a new filter row
2. **Select Field** — dropdown shows filterable columns for the selected source table (driven by `filter_config.json`)
3. **Select Operator** — operators change based on the field's data type:
   - **String fields:** equals, not equals, in list, not in list, contains, starts with
   - **Numeric fields:** =, ≠, >, ≥, <, ≤, between
   - **Date fields:** equals, after, before, between
4. **Enter Value** — for `in`/`not in`, use comma-separated values; for `between`, use `min,max`
5. **Match Logic** — choose ALL conditions (AND) or ANY condition (OR)
6. **Remove** — click the × button to remove a condition

Filters are saved as JSON in the database and applied automatically during batch execution.

---

## 9. Allocation Rules — Detail (with Filters)

**URL:** `/rules/<rule_id>`

View a rule's full configuration, including saved data filters.

![Rule Detail with Filters](images/18_rule_detail_with_filters.png)

**Key elements:**
- Full rule configuration (source, lookup, output, join key)
- **Data Filters** section — shows the saved filter logic (AND/OR) and conditions table
- **Toggle Active/Inactive** — enable or disable the rule without deleting it
- **Delete Rule** — permanently remove the rule
- **Allocation ratios preview** — shows the APPROVED allocation ratios that this rule would use

---

## 10. Batch Execution

**URL:** `/batch`

Run allocation rules against processed data and view past batch runs.

![Batch Execution](images/06_batch_execution.png)

**How to use:**
1. **Select a Rule** — choose from active allocation rules
2. **As-of Date** — the date to filter source data
3. **Click Run Allocation** — executes the Pandas-based "shredding" engine

**What happens during execution:**
- Source data is read from the configured table (filtered by date)
- **Data filters are applied** — if the rule has filter conditions, only matching rows are included
- Allocation ratios are looked up from the configured lookup table
- A left join matches source rows to ratios by the join key
- Balance and income columns are multiplied by the ratio
- Results are written to the output table (fct_mgmt_ledger)
- Orphan records (no matching ratio) are handled per config

**Past batch runs** are listed below with status, source/output row counts, and links to execution logs.

---

## 11. Batch Execution — Detail

**URL:** `/batch/<batch_id>`

View details of a completed batch run.

![Batch Detail](images/14_batch_detail.png)

**Key elements:**
- Batch metadata (rule used, as-of date, status, timestamps)
- Source and output row counts
- Link to the full execution log

---

## 12. Reports — Index

**URL:** `/reports`

Hub page with links to all available reports.

![Reports Index](images/07_reports_index.png)

**Available reports:**
- **Management Ledger** — aggregated allocation results
- **Operations Report** — system activity summary
- **Database Table Browser** — browse and edit any database table
- **Execution Log** — linked from batch detail pages

---

## 13. Management Ledger Report

**URL:** `/reports/ledger`

The primary output report

![Management Ledger](images/08_mgmt_ledger.png)

**How to use:**
1. **Group By** — choose a dimension: Org Unit, Product, Customer, or Account
2. **Batch Run** — filter to a specific batch or view all
3. **Click Filter** — refresh the results

**Results table shows:**
- Dimension value (e.g., target_org_unit_id)
- **Total Balance** — sum of allocated balances
- **Total Income** — sum of allocated interest income
- **Row Count** — number of output records in the group

This report shows how financial balances have been redistributed from legal/booking entities to management units.

---

## 14. Operations Report

**URL:** `/reports/operations`

System activity and health overview.

![Operations Report](images/09_operations.png)

**Key elements:**
- Upload activity by type and status
- Batch execution history
- Record counts across key tables
- System health indicators

---

## 15. Database Table Browser

**URL:** `/reports/tables`

Browse, search, and edit data in any database table.

![Table Browser](images/10_table_browser.png)

**How to use:**
1. **Select a table** from the dropdown — all 13 database tables are listed
2. **Click Browse** — view the table's data with pagination

---

## 16. Table Browser — Data View

**URL:** `/reports/tables?table=<table_name>`

View table data with pagination and inline editing.

![Table Data View](images/15_table_browse_data.png)

**Key elements:**
- **Table selector** — switch between tables
- **Column headers** — all columns in the selected table
- **Data rows** — paginated (configurable page size)
- **Edit / Delete** — inline actions for each row
- **Pagination** — navigate through large tables

Useful for verifying dimension data, checking staged records, or inspecting allocation results.

---

## 17. Test Data Generator

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

## 18. User Management

**URL:** `/admin/users` (Admin only)

Create, edit, and manage system users.

**Key elements:**
- **User list** — shows username, display name, group memberships, effective permissions (Can Make / Can Check), and active status
- **New User** — create a user with username, display name, password, and group assignments
- **Edit User** — change display name, reset password, toggle active status, reassign groups

Users authenticate via username/password. Each user's permissions are derived from their group memberships — there are no per-user permission flags.

**How to use:**
1. Click **New User**
2. Enter username, display name, and password
3. Select one or more groups (each shows its permission flags: [Make], [Check], [Admin])
4. Click **Create User**

---

## 19. Group Management

**URL:** `/admin/groups` (Admin only)

Create and manage permission groups.

**Key elements:**
- **Group list** — shows name, description, permission flags (Can Make, Can Check, Admin), active status, and member count
- **New Group** — create a group with name, description, and permission checkboxes
- **Edit Group** — modify description, permissions, or active status

**Permission flags:**

| Flag | Effect |
|---|---|
| **Can Make** | Users in this group can create and submit uploads for review |
| **Can Check** | Users in this group can approve or reject uploads (4-Eyes Principle) |
| **Admin** | Users in this group can access `/admin` to manage users and groups |

A user's effective permissions are the union of all their groups' permissions. For example, a user in both "Makers" and "Checkers" groups can both create and approve uploads (though not their own — 4-Eyes still applies).

---

## End-to-End Workflow Summary

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│   Login      │────>│  Test Data   │────>│  Upload File │────>│   Approve    │────>│  Create Rule │────>│ Run Batch    │
│   (any user) │     │  Generator   │     │  (Maker)     │     │  (Checker)   │     │              │     │ Allocation   │
└─────────────┘     └──────────────┘     └──────────────┘     └─────────────┘     └──────────────┘     └──────────────┘
                                                                                                             │
                                                                                                             ▼
                                                                                                      ┌──────────────┐
                                                                                                      │  View Ledger │
                                                                                                      │  Report      │
                                                                                                      └──────────────┘
```

1. **Login** as maker1 (or any user with Maker permissions)
2. **Generate** test data (or prepare your own Excel/CSV files)
3. **Upload** files via Data Upload — validation runs automatically, logged-in user is the Maker
4. **Login** as checker1 (or any user with Checker permissions, different from the Maker)
5. **Approve** uploads through the Maker/Checker workflow (4-Eyes + group permission enforcement)
6. **Create** an allocation rule defining the source → lookup → output mapping, with optional data filters
7. **Execute** a batch run to allocate balances using the rule (filters are applied automatically)
8. **Review** results in the Management Ledger Report
