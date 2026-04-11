# Manual Data Load Specification — BankPFT

## 1. Executive Summary
The Manual Data Load module provides a robust, configuration-driven interface for importing Excel (.xlsx) and CSV data into the platform. It enforces strict data governance through a multi-stage validation engine and a mandatory Maker/Checker (4-Eyes Principle) approval workflow.

---

## 2. Configuration-Driven Framework
The module is entirely driven by the `upload_config.json` file. This allows for adding new data types (e.g., new instrument schemas or reference tables) without modifying backend Python code.

### 2.1 Schema Definition
For each data type, the configuration defines:
- **Target Staging Table**: Where the data is physically stored after approval.
- **Required & Optional Columns**: Dictates the expected Excel/CSV header structure.
- **Data Types & Type-Casting**: Ensures date strings and numeric fields are correctly parsed.
- **Unique Keys**: Prevents duplicate records within the same as-of date.

---

## 3. Data Lifecycle & Workflow (4-Eyes Principle)
To ensure data integrity, every upload follows a formal workflow:

1.  **UPLOAD (Maker)**: A user with `Can Make` permissions selects a data type and uploads a file.
2.  **VALIDATION**: The engine performs automated checks (see Section 4). If validation fails, the file is rejected immediately with a detailed error report.
3.  **STAGING (DRAFT)**: Validated data is stored in the `data_file` and `data_file_row` metadata tables with a `DRAFT` status.
4.  **REVIEW (Checker)**: A different user with `Can Check` permissions reviews the upload.
5.  **APPROVAL/REJECTION**:
    - **Approve**: Data is physically moved from the metadata tables to the linked **Staging Table** (e.g., `stg_inst_data`).
    - **Reject**: The upload is marked as `REJECTED` and no physical data movement occurs.

---

## 4. Validation Engine
The module supports several granular validation rules out of the box:

| Rule | Description |
| :--- | :--- |
| `required_columns` | Checks for the existence of all mandatory headers. |
| `null_check` | Ensures no empty values in required fields. |
| `unique_key` | Verifies that the specified unique identifier (e.g., `account_id`) is not repeated. |
| `dimension_lookup` | Cross-references foreign keys against dimension tables (e.g., `dim_product`). |
| `numeric_range` | Validates that values fall within defined Min/Max bounds. |
| `ratio_sum` | Ensures groups of records sum to exactly 1.0 (e.g., Allocation Ratios). |

---

## 5. High-Resolution Application Interface

![Manual Data Load List](images/v2_manual_data_load.png)
*Figure 1: Data Load Inbox — Monitoring Upload Status*

---

## 6. Post-Approval Hooks (Automation)
The system supports automated actions triggered immediately upon successful approval:

- **Run Allocation Rules**: Automatically triggers specific calculation rules after source data is approved.
- **Execute Stored Procedures**: Refreshes calculation caches or materialized views after reference data (e.g., Ratios) is updated.

---

## 7. Technical Implementation
- **Backend**: `app/services/upload_service.py` (Core validation logic)
- **API**: `app/routes/upload.py`
- **Metadata Storage**:
    - `data_file`: Stores upload metadata (filename, status, counts).
    - `data_file_row`: Temporary storage for unapproved rows.
- **Physical Staging**: Data is inserted using highly optimized bulk-loading techniques (SQLAlchemy `insert().values()`) once approved.
