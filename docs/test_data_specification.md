# Test Data Generation Specification — BankPFT

## 1. Executive Summary
The Test Data module provides a procedural framework for seeding the BankPFT platform with realistic, high-volume financial data. It allows developers and business users to verify engine performance, validate reporting logic, and test manual data load workflows without requiring access to sensitive production data.

---

## 2. Hierarchical Generation Model
To ensure database integrity, the generation engine follow a strictly ordered hierarchical flow:

1.  **Layer 1: Dimension Masters**: Procedural creation of Org Units, Products, and Customers.
2.  **Layer 2: Account Mapping**: Linking Customers and Products to specific Org Units to create realistic account headers.
3.  **Layer 3: Transactional Data**: Generation of temporal instrument-level and GL-level balances linked to the Master Layer.
4.  **Layer 4: Configuration Seeders**: Auto-provisioning of Allocation Rules and FTP Pricing Models for quick-start environments.

---

## 3. Procedural Generators

### 3.1 Dimensions & Master Data
- **Org Units**: Creates a Headquarters structure with 10 leaf-node branches.
- **Products**: Provisions 5 standard retail/corporate products (Personal Loan, Mortgage, etc.).
- **Customers**: Randomly generates 50 customers across different segments (Retail, SME, Private Banking).

### 3.2 Dynamic Instrument Data
- **Engine**: `generate_instrument_data()`
- **Volume**: 500+ records per as-of date.
- **Logic**: For every account, it generates 8-12 transaction rows with randomized `balance` and `interest_income` values, ensuring a diverse dataset for testing allocation splitting.

### 3.3 Interest Rate Curves
- **Engine**: `generate_interest_rates()`
- **Scope**: Generates a 30-day historical window for 3 rate codes (e.g., SOFR).
- **Structure**: Populates multiple tenors (1D, 1M, 3M, 1Y) with slight daily fluctuations for realistic FTP testing.

---

## 4. Excel Template Generator (Data Injection)
The system procedurally creates Excel templates for external manual load testing, allowing users to verify the "Maker/Checker" workflow with valid system keys.

### 4.1 Static Templates
- **Description**: Empty Excel files with headers matching the `upload_config.json`.
- **Use Case**: Fresh data entry testing.

### 4.2 Template with Data (Injected Master Data)
The engine can "Inject" active system keys into templates to create frictionless test files:
- **Allocation Template**: Retrieves `DimCustomer` and `DimOrgUnit` records from the database and generates randomized allocation rows (2-4 targets per customer) that are mathematically guaranteed to sum to 1.0.
- **Interest Rate Template**: Generates a 30-day historical curve for all system rate codes (e.g., SWAP_RATE), ready for immediate upload to the staging tables.
- **Validation**: This feature ensures that the downloaded file will pass all foreign-key and business-logic validation checks upon re-upload.

---

## 5. Deployment & Seeding (4-Eyes Bypass)
While standard production uploads require a Maker/Checker workflow, the Test Data Generator inserts data directly with an `APPROVED` status.

| Action | Technical Command (Backend) | UI Command |
| :--- | :--- | :--- |
| Seed Rules | `seed_default_allocation_rules()` | "Seed Default Rules" |
| Generate FTP | `generate_ftp_configs()` | "Generate FTP Config" |
| Refresh Master | `generate_master_data()` | "Reset Master Data" |

---

## 6. Technical Implementation
- **Core Library**: `random` (for stochastic value generation), `pandas` (for Excel template construction).
- **Service Logic**: `app/services/testdata_service.py`.
- **Infrastructure**: All generation runs in the context of a `BatchRun` or `UploadBatch` to ensure the resulting data is searchable via the platform's standard traceability tools.
