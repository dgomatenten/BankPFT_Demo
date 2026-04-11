# Allocation Rule Specification — BankPFT

## 1. Executive Summary
The Allocation Rule engine is the primary computational core of the BankPFT platform. It transforms processed staging data into multi-dimensional management ledger entries. It supports ratio-based splitting, static distribution, and structural data shredding (multiplexing) into granular Financial Elements.

---

## 2. Functional Core: Allocation Methods
The engine supports three distinct allocation strategies defined at the rule level:

### 2.1 Ratio-Based Allocation (`RATIO`)
- **Logic**: Performs a left join between the **Source Table** and a **Lookup Table** (e.g., `ref_static_allocation`) using a user-defined **Join Key**.
- **Execution**: The balance is multiplied by the ratio from the lookup table. Total ratios per join-key group must sum to 1.0.
- **Orphan Handling**: Rows with no match in the lookup table are posted to the output with a `ratio = 1.0` and a default "Orphan" dimension flag.

### 2.2 Static Distribution (`DISTRIBUTION`)
- **Logic**: Similar to Ratio-Based, but pulls ratios from the `ref_static_distribution` table filtered by a specific **Distribution Driver** name.
- **Use Case**: Best for high-level pools (e.g., "IT Cost Pool Q1") that are shared across many rules.

### 2.3 Static Allocation (`STATIC`)
- **Logic**: No join performed. Maps source rows 1:1 to the output table with a hardcoded ratio of 1.0.
- **Use Case**: Used for direct reclassification or simple data migration from staging to fact.

---

## 3. Allocation Operators & Mathematical Logic

The engine defines the relationship between input and output using a mathematical operator. This ensures accounting integrity and allows for complex fractional splitting.

### 3.1 The Allocation Equation
The fundamental logic applied during the calculation is:
**`Source Balance` × `Operator (Ratio)` = `Output Amount`**

### 3.2 Ratio Definition
The operator can be sourced in three ways:
- **Fixed Operator**: A static number (usually `1.0`) applied to all rows.
- **Lookup Operator**: A variable percentage (e.g., `0.25`) retrieved from a reference table based on a Join Key.
- **Balanced Entry Operator**: For 'Both' entry mode, the engine applies `1.0` to the Debit and `-1.0` to the Credit to ensure a zero-sum impact on the ledger.

---

## 4. High-Resolution Application Interface

![Allocation Rule List](images/v2_allocation_rules_list.png)
*Figure 1: Allocation Rule Management Console*

![New Allocation Rule](images/v2_allocation_rule_new.png)
*Figure 2: Multi-Dimensional Rule Definition Form*

---

## 5. Multi-Dimensional Mapping & Governance

### 4.1 Source Dimension Filters
Allows for granular selection of source data. Dimensions (e.g., Product, Org Unit, Region) can be set to "All Members" or "Specific Members" (comma-separated list).

### 4.2 Output Mapping (Debit & Credit)
For every output dimension, the engine supports three mapping modes:
- **Same as Source**: Preserves the original dimension value.
- **From Lookup**: Extracts the value from a specific column in the joined lookup table.
- **Fixed Value**: Hardcodes a specific member (e.g., a Clearing Account ID) for all results.

### 4.3 Entry Mode Orchestration
- **Both (Debit + Credit)**: Generates two rows per match to maintain balanced accounting records.
- **Debit Only**: Only the target-side entry is generated.
- **Credit Only**: Only the source-side reversal is generated.

---

## 6. Structural Data Shredding (Financial Elements)
A unique feature of the BankPFT engine is its ability to structurally multiplex source balances into distinct Financial Elements.

If the **Output Model** (e.g., `fct_mgmt_ledger`) contains the `financial_element` column, the engine performs an **Unpivot Transformation**:
- For a single source record, it generates multiple output rows (e.g., `100 - BAL`, `120 - II`, `140 - COF`).
- The logic ensures that each component row is individually mapped and traceable to the same parent allocation ID.

---

## 7. Technical Implementation
- **Language**: Python 3.x
- **Core Library**: Pandas (for high-performance Vectorized Joins and Unpivots)
- **Database**: PostgreSQL (SQLAlchemy ORM)
- **Idempotency**: The engine automatically clears existing data for the same `rule_id` and `as_of_date` before execution, ensuring re-runs do not duplicate data.
