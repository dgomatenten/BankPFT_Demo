# REST API Specification — BankPFT

## 1. Executive Summary
The BankPFT REST API (v1) allows for remote orchestration, data ingestion, and rule management. It is designed for integration with enterprise scheduling tools (e.g., Apache Airflow, Jenkins) and external data lakes.

---

## 2. Authentication & Headers
All requests must be made over HTTPS and require **HTTP Basic Authentication** using valid platform credentials.

- **Base URL**: `http://<server-ip>:5000/api/v1`
- **Content-Type**: `application/json`
- **Auth**: `admin:password` (Base64 encoded)

---

## 3. Batch Orchestration API
These endpoints control multi-task pipelines (Grouped Allocations, FTP, and Imports).

### 3.1 List Batch Definitions
`GET /batch/definitions`
- **Description**: Returns all active multi-task pipelines.
- **Response**: List of definitions with `definition_id` and `step_count`.

### 3.2 Execute Batch Definition
`POST /batch/definitions/<definition_id>/run`
- **Payload**: `{"as_of_date": "2026-04-11"}` (Optional, defaults to today)
- **Description**: Triggers a non-blocking background execution of the full pipeline.
- **Response**: Returns a unique `execution_id`.

### 3.3 Monitor Batch Execution
`GET /batch/executions/<execution_id>`
- **Description**: Returns the real-time status of the execution header and per-step results.
- **Status Values**: `RUNNING`, `COMPLETED`, `FAILED`, `PARTIAL`.

---

## 4. Allocation & FTP Rule Lifecycle
Manage and export/import calculation logic as portable JSON objects.

### 4.1 Export Allocation Rules
`GET /batch/rules`
- **Description**: Returns all active rules with full configuration (Dimensions, Filters, Methods).

### 4.2 Import Allocation Rule
`POST /rules/import`
- **Payload**: Full Rule JSON (same schema returned by export).
- **Description**: Creates a new rule or updates an existing structure.

### 4.3 Export FTP Models
`GET /ftp/models`
- **Description**: Returns all FTP models and their internal pricing rules (COF, LP, CLP).

### 4.4 Import FTP Configuration
`POST /ftp/config/import`
- **Payload**: FTP Process/Model JSON array.
- **Description**: Bulk imports FTP pricing environments.

---

## 5. Data Lifecycle API
Manual and automated data ingestion.

### 5.1 Trigger Data Import
`POST /datafile/import`
- **Payload**: `{"format_id": "GL", "filename": "gl_data_q1.csv"}`
- **Note**: The file must be pre-placed in the `uploads/inbox/` directory.

### 5.2 Trigger Data Export
`POST /datafile/export`
- **Payload**: `{"export_id": "MGMT_LEDGER", "as_of_date": "2026-04-11"}`

---

## 6. Error Handling
The API uses standard HTTP status codes:
- **200/201**: Success / Created.
- **401**: Unauthorized (Invalid or missing Basic Auth).
- **400**: Bad Request (Invalid JSON or missing fields).
- **404**: Resource Not Found (Incorrect ID).
- **422**: Unprocessable Entity (Execution failed due to logical errors).

All errors return a JSON envelope: `{"error": "Description of the failure"}`.
