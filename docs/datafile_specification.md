# Data File Specification — BankPFT

## 1. Overview
BankPFT supports import and export of data files for financial processes. File formats are defined in JSON configs under `app/config/datafile/`. Supported types include fixed-width and delimited (CSV/pipe) files. Files are processed via the Data File Management module and REST API.

---

## 2. File Types & Locations
- **Inbox:** `instance/datafile_inbox/` — Place files here for import.
- **Outbox:** `instance/datafile_outbox/` — Exported files are written here.

---

## 3. Import File Specifications

### 3.1 Instrument Data (CSV)
- **Config:** `import_inst_csv.json`
- **Format:** Comma-separated, no header (fields mapped by index)
- **Fields:**
  1. `account_id` (string)
  2. `customer_id` (string)
  3. `product_code` (string)
  4. `org_unit_id` (string)
  5. `as_of_date` (date, `%Y-%m-%d`)
  6. `balance` (float, cents → dollars: `float(value)/100.0`)
  7. `interest_income` (float, cents → dollars)
  8. `transaction_number` (string)

### 3.2 Instrument Data (Fixed Length)
- **Config:** `import_inst_fixed.json`
- **Format:** Fixed-width, 120 chars/record, skip 1 header row
- **Fields:** (start, length)
  - `account_id` (1, 20)
  - `customer_id` (21, 15)
  - `product_code` (36, 10)
  - `org_unit_id` (46, 15)
  - `as_of_date` (61, 10, `%Y-%m-%d`)
  - `balance` (71, 20, cents → dollars)
  - `interest_income` (91, 20, cents → dollars)

### 3.3 Loan Data (Fixed Length)
- **Config:** `import_loan.json`
- **Format:** Fixed-width, 120 chars/record, skip 1 header row
- **Fields:** (start, length)
  - `account_id` (1, 15) — from `loan_id`
  - `customer_id` (16, 15) — from `borrower_id`
  - `product_code` (31, 10, uppercase)
  - `org_unit_id` (41, 10, `BR` + zero-padded)
  - `as_of_date` (51, 8, `%Y%m%d`)
  - `balance` (59, 18, cents → dollars)
  - `interest_income` (77, 15, cents → dollars)

### 3.4 GL Data (Fixed Length)
- **Config:** `import_gl_fixed.json`
- **Format:** Fixed-width, 100 chars/record, skip 1 header row
- **Fields:** (start, length)
  - `gl_account` (1, 20)
  - `org_unit_id` (21, 15)
  - `as_of_date` (36, 10, `%Y-%m-%d`)
  - `debit` (46, 20, cents → dollars)
  - `credit` (66, 20, cents → dollars)
  - `balance` (86, 15, cents → dollars)

### 3.5 GL Data (Pipe Delimited)
- **Config:** `import_gl_pipe.json`
- **Format:** Pipe-separated, header row present, fields mapped by name
- **Fields:**
  - `gl_account` (string)
  - `org_unit_id` (string)
  - `as_of_date` (date, `%Y-%m-%d`)
  - `debit` (float, cents → dollars)
  - `credit` (float, cents → dollars)
  - `balance` (float, cents → dollars)

---

## 4. Export File Specifications

### 4.1 Processed Instruments (Fixed Length)
- **Config:** `export_inst_proc.json`
- **Format:** Fixed-width, header included
- **Fields:** (start, length)
  - `account_id` (1, 20)
  - `customer_id` (21, 15)
  - `product_code` (36, 10)
  - `org_unit_id` (46, 15)
  - `as_of_date` (61, 10, `%Y-%m-%d`)
  - `balance` (71, 20, dollars → cents, rounded)
  - `interest_income` (91, 20, dollars → cents, rounded)

### 4.2 Allocation Results (Fixed Length)
- **Config:** `export_alloc_result.json`
- **Format:** Fixed-width, header included, only `DEBIT` entries
- **Fields:** (start, length)
  - `batch_run_id` (1, 36)
  - `as_of_date` (37, 10, `%Y-%m-%d`)
  - `source_account_id` (47, 20)
  - `customer_id` (67, 15)
  - `target_org_unit_id` (82, 15)
  - `allocated_balance` (97, 20, 2 decimals)

---

## 5. Validation & Transformations
- **Validation:** Required columns, null checks, unique keys, dimension lookups, numeric ranges (see `upload_config.json`).
- **Transformations:** Use expressions like `float(value)/100.0`, `upper(trim(value))`, or custom logic as defined in each config.
- **Date Formats:** Strictly enforced per field.

---

## 6. Reference
- See `app/config/datafile/*.json` for all file format definitions.
- See `app/config/upload_config.json` for data type validation and workflow.
- See README and WALKTHROUGH for user flows and upload instructions.
