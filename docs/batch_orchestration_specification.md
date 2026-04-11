# Batch Orchestration Specification — BankPFT

## 1. Executive Summary
The Batch Orchestration module is the platform's central nervous system, responsible for coordinating complex, multi-stage financial calculation pipelines. It allows users to group individual tasks (Allocations, FTP, Data Imports/Exports) into a single, ordered execution unit with granular error handling and real-time monitoring.

---

## 2. Batch Definition (Static Configuration)
A **Batch Definition** acts as a blueprint for a pipeline. It consists of one or more **Batch Tasks** ordered by a sequence number.

### 2.1 Key Attributes
- **Name & Description**: Identifiers for the pipeline.
- **Continue on Error**: Boolean flag. If `True`, the batch proceeds to the next step even if a previous step fails. If `False`, the entire pipeline halts on failure.
- **Step Order**: Determines the exact execution sequence.

---

## 3. Multi-Task Orchestration Flow
The orchestration follows a "Prepare-then-Execute" pattern to ensure all metadata is initialized before the first task begins.

1.  **Preparation**: The engine clones the definition's tasks into `BatchExecutionStep` records in a `PENDING` state.
2.  **Dispatching**: The `batch_executor` iterates through steps. For each step, it resolves dynamic parameters (e.g., `as_of_date` tokens) and calls the specific sub-engine.
3.  **Status Propagation**: As each step completes, its individual status (`COMPLETED`, `FAILED`) is bubbled up to the top-level `BatchExecution` record.

---

## 4. Supported Task Types
The orchestrator is architected to handle diverse computational loads:

| Task Type | Description | Sub-Engine |
| :--- | :--- | :--- |
| `ALLOCATION` | Python-based ratio splitting. | `allocation_engine.py` |
| `ALLOCATION_SP` | High-performance SQL-based allocation. | `sp_run_allocation (PostgreSQL)` |
| `FTP` | Funds Transfer Pricing calculations. | `ftp_engine.py` |
| `DATAFILE_IMPORT` | Automated CSV/Excel staging load. | `datafile_service.py` |
| `DATAFILE_EXPORT` | Result extraction to CSV/Excel. | `datafile_service.py` |
| `CUSTOM_SP` | Execution of any registered Stored Procedure. | `sp_runner.py` |

---

## 5. High-Resolution Batch Monitoring

![Batch Monitor](images/v2_dashboard.png)
*Figure 1: Batch Monitor Dashboard — Real-time execution status*

### 5.1 Real-Time Observability
The **Batch Monitor** provides three levels of transparency:
1.  **High-Level Status**: Color-coded badges (`RUNNING`, `COMPLETED`, `FAILED`, `PARTIAL`).
2.  **Step-Level Progress**: A progress bar and itemized list show which specific step is currently active.
3.  **Live Console**: Users can view the consolidated `BatchLogger` output as it is written to the `/instance/batch_logs/` directory.

---

## 6. Operation Variables (Dynamic Logic)
The orchestrator supports **Operation Variables** (e.g., `processing_date`) which can override the execution date for all tasks in a batch. This allows for "What-if" analysis and historical re-runs without modifying task configurations.

---

## 7. Technical Implementation (Asynchronous Design)
To ensure high availability and responsiveness, the orchestrator MUST follow an asynchronous, non-blocking execution model:

- **Non-blocking Dispatch**: Upon clicking "Run Batch", the system immediately prepares the records and returns a "Success" response to the UI. It does NOT wait for the tasks to finish.
- **Background Processing**: The actual execution phase happens in a dedicated background thread or worker process.
- **Status Monitoring**: Users are redirected to the **Batch Monitor** (Section 5) to track real-time progress. The UI pulls status updates via a JSON polling endpoint (`/monitor/status`) rather than holding a long-lived synchronous connection.
- **Persistence**: 
    - `batch_definition`: The blueprint.
    - `batch_execution`: The run header.
    - `batch_execution_step`: The individual task result tracker.
- **API Support**: Includes REST endpoints (`/api/run-by-name`) for external triggering via cron or Airflow.
