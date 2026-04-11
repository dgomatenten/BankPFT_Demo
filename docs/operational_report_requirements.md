# Operational Report Requirements — BankPFT

## 1. Executive Summary
The Operational Report system provides end-to-end traceability for every transaction processed by the BankPFT platform. It ensures that auditors and business analysts can bridge the gap between financial source data (Staging/Processing) and the finalized Management Ledger (Fact) by exposing the exact ratios, drivers, and mathematical logic applied during execution.

---

## 2. Core Traceability Linkages
To maintain a forensic audit trail, the system relies on the following primary keys and foreign keys:

| Key Field | Purpose |
| :--- | :--- |
| `batch_run_id` | Links output rows in `fct_mgmt_ledger` to a specific execution instance (`batch_run` table). |
| `allocation_id` | Links output rows back to the specific `allocation_rule` and its corresponding lookup drivers (e.g., `allocation_id` in `ref_static_allocation`). |
| `source_account_id` | Preserves the original identifier from the source staging table for granular instrument-level debugging. |
| `as_of_date` | Ensures temporal alignment across all source, driver, and output datasets. |

---

## 3. Data Provenance Flow

### 3.1 Input Data Creation
- **Source Selection**: The engine filters rows from `proc_gl_data` or `proc_inst_data` based on the `as_of_date` and user-defined dimension filters (Org Unit, Product, Business Line).
- **Snapshot**: The exact count and total balance of selected source records are persisted in the `batch_run` metadata table.

### 3.2 Ratio & Driver Application
- **Method Retrieval**: The engine identifies the `allocation_method` (Ratio, Distribution, or Static) from the associated rule.
- **Lookup Join**: For Ratio/Distribution methods, the engine performs a vectorized join with reference tables (`ref_static_allocation`, `ref_static_distribution`). 
- **Driver Persistence**: The specific ratio applied (e.g., `0.35`) and the target dimensions defined in the driver are mapped to the final output row.

### 3.3 Output Generation
- **Balanced Entries**: For every match, the engine generates a **Debit** (allocated target) and a **Credit** (source reversal) entry.
- **Financial Element Mapping**: If the rule requires shredding, the source balance is multiplexed into distinct Financial Elements (e.g., BAL, II, COF) during the output write phase.

---

## 4. Audit & Logging Requirements

### 4.1 SQL-Level Traceability
For batch runs executed via Stored Procedures (`ALLOCATION_SP`), the system must populate the `sp_alloc_log` table with:
- **Rendered SQL**: The exact `INSERT...SELECT` statements used.
- **Impact Analysis**: The row count affected by each phase of the allocation.
- **Time Profiling**: Start/End timestamps for source extraction, calculation, and cleanup.

### 4.2 Application-Level Logging
For Python-based engine runs, `BatchLogger` must persist:
- **Transformation Steps**: Log every join operation and unpivot filter.
- **Exceptions**: Stack traces for skipped rows or data-type mismatches.
- **Log Path**: `/instance/batch_logs/batch_<batch_id>.log`.

---

## 5. Traceability Interface (The 3-Panel View)
The operational report UI must present a unified view of the lifecycle of a single rule run:

1.  **Source Panel**: Shows the filtered staging data *before* allocation.
2.  **Driver Panel**: Shows the matching ratios from the reference tables.
3.  **Output Panel**: Shows the resulting management ledger entries with calculated balances.

---

## 6. Functional Scenarios
- **Scenario: "Where did this row come from?"**: User searches by `batch_id` and drill-down to see the 3-panel trace for a specific account.
- **Scenario: "Why is there an orphan?"**: User filters the operation report for `orphan_count > 0` to identify missing ratios in the driver tables.
- **Scenario: "Audit Trail"**: Auditor views the **SQL Log** to verify that the mathematical operator (Ratio) was applied consistently to all qualifying source records.
