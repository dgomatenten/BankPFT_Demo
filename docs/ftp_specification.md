# Fund Transfer Pricing (FTP) Specification — BankPFT

## 1. Executive Summary
The Fund Transfer Pricing (FTP) engine provides a decoupled, multi-dimensional framework for calculating the internal cost of funds and liquidity premiums. Unlike monolithic FTP systems, BankPFT separates calculation logic (Models) from data execution (Processes), enabling granular component-based pricing (COF, LP, CLP) across diverse staging schemas.

---

## 2. Decoupled Architecture

### 2.1 FTP Models (The "What")
- **Conceptual Definition**: A model defines a set of pricing rules. Each rule maps a combination of dimensions (e.g., Product, Currency) to a mathematical calculation.
- **Components**: Supports structural pricing for **Cost of Funds (COF)**, **Liquidity Premium (LP)**, and **Contingent Liquidity Premium (CLP)**.

### 2.2 FTP Processes (The "How")
- **Conceptual Definition**: A process binds an FTP Model to a **Target DB Table** (e.g., `proc_inst_data` or `stg_gl_data`).
- **Orchestration**: When a process is executed, the engine loads all rules from the mapped model and applies them sequentially to the target table for a specific **As-of Date**.

---

## 3. High-Resolution Application Interface

![FTP Models](/home/dgoma/.gemini/antigravity/brain/1613df54-0db3-457c-97ac-ab34bb5ee73d/ftp_models_v2_1775917435750.png)
*Figure 1: FTP Calculation Models — Global Rulesets*

![Pricing Rule Definition](/home/dgoma/.gemini/antigravity/brain/1613df54-0db3-457c-97ac-ab34bb5ee73d/ftp_model_detail_v2_1775917439571.png)
*Figure 2: Pricing Matrix — Mapping Tenor and Average Periods*

![FTP Execution Processes](/home/dgoma/.gemini/antigravity/brain/1613df54-0db3-457c-97ac-ab34bb5ee73d/ftp_processes_v2_1775917443512.png)
*Figure 3: FTP Execution Processes — Staging Table Binding*

![Process Mapping Form](/home/dgoma/.gemini/antigravity/brain/1613df54-0db3-457c-97ac-ab34bb5ee73d/ftp_process_detail_v2_1775917447651.png)
*Figure 4: Binding Model to Physical Schema*

---

## 4. Calculation Methodology: Moving Average (`MOVING_AVG`)
The primary calculation method currently implemented is the **Moving Average**. 

### 4.1 Parameterization
- **Rate Code**: The interest rate index to pull (e.g., LIBOR, SOFR, SWAP).
- **Term & Mult**: The tenor point on the curve (e.g., 5 Years).
- **Average Period & Mult**: The lookback window (e.g., 3 Months).

### 4.2 Mathematical Execution
For each instrument, the engine:
1.  Identifies the relevant rule based on Product/Dimension matches.
2.  Fetches historical rates for the specified window leading up to the **As-of Date**.
3.  Calculates the simple average of these rates.
4.  Applies the resulting rate to the instrument's balance to calculate the transfer amount.

---

## 5. Structural Output & Component Pricing
The FTP engine is designed to multiplex its results into separate components. This allows for a deeper margin analysis:
- **COF**: Base Transfer Price.
- **LP**: Charge for liquidity mismatch.
- **CLP**: Charge for contingent liquidity stress.

Results are written back to the target table's FTP columns, which are then picked up by the **Allocation Engine** for unpivoting into the Management Ledger.

---

## 6. Execution Flow & Traceability
1.  **Selection**: Fetch active processes for the current batch.
2.  **Filtering**: Select rows in the target table matching the process-level filters and as-of date.
3.  **Calculation**: Multi-threaded calculation per instrument.
4.  **Audit**: Log every calculation attempt, including skipped instruments due to missing rate data or configuration.
