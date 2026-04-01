## **1\.1.Objective**

To build a plottype of  granular **Management Allocation System** that redistributes financial balances and income from a "Legal/Booking" level to a "Management" level. The system uses **Static Allocation Ratios** grouped by a unique **Allocation Identifier** to ensure full traceability and accounting integrity.

1. Data Model  
   1. Master Data , Dimensions   
      1. Org Unit  
      2. Account   
      3. Customer   
      4. Product   
   2. Staging /Processing   
      1. Insturment   
      2. GL  
      3. Lookup Tables   
   3. Result  
      1. Management Ledger   
2. Manual Data Load framework for  Static Allocation Ratio.   
   1. spreadsheet upload  
   2. Validation framework for input data  
   3. Maker/Cheker functionaliy  
   4. push to final target  
3. Allocation Rule configuration  
   1. configure source, Lookup table and output configuration   
   2. Source is Instrument, output is Management Ledger  
   3. list of rules and configuration UI  
4. Batch configuration   
   1. run the rule as batch   
5. Reporting  
   1. operation reporting   
      1. rule execution log  
   2. management ledger report.   
6. Test data generation engine  
   1. generate instrument, GL, master data test data  
   2. generate excel template to test Manual Data Load. 

## ---

## 

The primary goal is to redistribute financial balances (Instrument level) and General Ledger (GL) entries from their booking source to a target Management Ledger.

* **Granularity:** Calculations occur at the individual account/instrument level.  
* **Integrity:** Uses a unique **Allocation Identifier** to group splits, ensuring every dollar is traced from source to destination without "leakage."

## ---

**2\. Data Model (SQLAlchemy / SQLite)**

The data model is tiered to support a clean data pipeline: **Dimensions $\\rightarrow$ Staging $\\rightarrow$ Processing $\\rightarrow$ Results.**

### **2.1 Master Data & Dimensions**

These tables represent the "Golden Source" for validation.

| Table | Key Fields | Purpose |

| :--- | :--- | :--- |

| **Dim\_Org\_Unit** | org\_unit\_id, name, is\_leaf | Defines the hierarchy of branches/departments. |

| **Dim\_Product** | product\_code, name, is\_leaf | Defines the bank products (Loans, Deposits, etc.). |

| **Dim\_Customer** | customer\_id, name, segment | Master list of unique clients. |

| **Dim\_Account** | account\_id, customer\_id, product\_code | Mapping of specific accounts to customers/products. |

### **2.2 Staging & Processing Layer**

* **Staging (STG):** Raw, unvalidated data from Excel uploads.  
* **Processing (PROC):** Validated data that has passed referential integrity checks against Dimensions.

| Object | Staging Table | Processing Table |
| :---- | :---- | :---- |
| **Instrument** | STG\_INST\_DATA | PROC\_INST\_DATA |
| **General Ledger** | STG\_GL\_DATA | PROC\_GL\_DATA |

### **2.3 Lookup & Result Tables**

* **Ref\_Static\_Allocation (Lookup):** Stores the rules. Columns: allocation\_id, customer\_id, target\_org\_unit\_id, ratio, status.  
* **FCT\_Mgmt\_Ledger (Result):** The final output. Columns: as\_of\_date, allocation\_id, customer\_id, org\_unit\_id, allocated\_balance, source\_id.

## ---

**3\. Manual Data Load & Maker/Checker Workflow**

The system utilizes a **4-Eyes Principle** state machine to manage the lifecycle of data and rules.

### **3.1 State Machine Logic**

1. **Draft:** Maker uploads Excel or creates a rule.  
2. **Pending/Submitted:** Maker "submits" for review. Validation runs here.  
3. **Approved:** Checker verifies. Data moves from STG to PROC.  
4. **Rejected:** Checker sends back to Maker for corrections.  
5. **Processed:** Batch has been executed and results are in the Ledger.

### **3.2 Spreadsheet Upload Framework**

* **Format:** Support .xlsx and .csv.  
* **Validation Framework:**  
  * **Technical:** Check for nulls, data types (Date/Numeric), and duplicate IDs.  
  * **Dimension Check:** Verify that Org Units, Products, and Customers exist in Master Data.  
  * **Ratio Check:** For a unique allocation\_id and customer\_id, the sum of ratio must equal exactly **1.0 (100%)**.

## ---

**4\. Allocation Rule Configuration**

This module allows users to configure the "Shredding" logic through a dedicated UI.

* **Source:** Instrument Data (Granular).  
* **Lookup Table:** Static Allocation Ratios defined by the user.  
* **Output:** Management Ledger.  
* **UI Features:**  
  * A list view of all active/draft rules.  
  * A configuration screen to map a customer\_id to multiple org\_unit\_ids with corresponding ratios.  
  * Real-time validation on the UI that turns "Green" only when the total ratio hits 100%.

## ---

**5\. Batch Configuration & Execution Engine**

The "Brain" of the system uses **Pandas** to perform high-speed redistribution.

### **5.1 The "Shredding" Logic**

When a batch is triggered, the engine performs the following calculation for every record:

$$\\text{Allocated Value} \= \\text{Source Balance} \\times \\text{Static Allocation Ratio}$$  
**Logic Flow:**

1. Load PROC\_INST\_DATA for the selected period.  
2. Join with REF\_STATIC\_ALLOCATION on customer\_id.  
3. For every match, create a new row in the Management Ledger.  
4. If no match is found (Orphan record), allocate 100% to the original "Legal" Org Unit.

## ---

**6\. Reporting & Operational Monitoring**

1. **Operation Reporting:** A dashboard showing the status of current batches (Uploaded, Validated, Error, Approved).  
2. **Rule Execution Log:** A detailed audit trail showing:  
   * *Who* approved the rule.  
   * *How many* rows were processed.  
   * *Total Sum* of source vs. total sum of output (to ensure zero data loss).  
3. **Management Ledger Report:** A final pivot table showing Profit/Loss by Org\_Unit\_ID, Product, and Customer.

## ---

**7\. Test Data Generation Engine**

To facilitate rapid prototyping and testing:

* **Master Data Generator:** Creates 10 dummy Org Units, 5 Products, and 50 Customers.  
* **Instrument/GL Generator:** Creates 500+ randomized account records with varying balances.  
* **Excel Template Generator:** A utility that exports "Empty" Excel files with the correct headers and dropdown validations for manual data load testing.

## ---

**8\. Technical Stack Implementation (Docker/Flask)**

* **Containerization:** The entire app (Flask, SQLite, and Python dependencies) is packaged in a **Docker** container for "Plug and Play" deployment.  
* **Backend:** Flask handles the API routes for the Maker/Checker workflow.  
* **ORM:** SQLAlchemy manages the SQLite database, ensuring schema consistency.  
* **Processing:** Pandas is used as the primary engine for all bulk data transformations and Excel parsing.

