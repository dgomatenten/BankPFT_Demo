-- ============================================================
-- 07_workflow.sql  —  Upload, Allocation Rule & Batch Workflow Tables
-- Tables:
--   upload_batch          — Maker/Checker upload lifecycle
--   allocation_rule       — Allocation rule configuration
--   batch_run             — Single-rule allocation execution
--   batch_definition      — Named multi-task batch template
--   batch_task            — Ordered steps in a batch definition
--   batch_execution       — One execution of a batch definition
--   batch_execution_step  — Per-task result within a batch execution
--   post_approval_log     — Actions triggered on upload approval
--   sp_run                — Stored-procedure invocation audit
-- ============================================================

-- ──────────────────────────────────────────────────────────
-- Upload batch lifecycle (Maker/Checker)
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS upload_batch (
    id               VARCHAR(36)  PRIMARY KEY,  -- UUID
    data_type        VARCHAR(20)  NOT NULL,      -- INSTRUMENT | GL | ALLOCATION | ...
    filename         VARCHAR(255) NOT NULL,
    row_count        INTEGER      NOT NULL DEFAULT 0,
    error_count      INTEGER      NOT NULL DEFAULT 0,
    errors_json      JSONB,
    maker_comment    TEXT,
    checker_comment  TEXT,
    -- MakerCheckerMixin
    status           VARCHAR(20)  NOT NULL DEFAULT 'DRAFT',
    maker_id         VARCHAR(50)  NOT NULL,
    checker_id       VARCHAR(50),
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  upload_batch           IS 'Tracks every file upload through the Maker/Checker approval lifecycle.';
COMMENT ON COLUMN upload_batch.data_type IS 'Content type of the upload: INSTRUMENT, GL, ALLOCATION, ORG_RECLASS, INTEREST_RATE, STATIC_DIST, STATIC_ALLOC.';
COMMENT ON COLUMN upload_batch.status    IS 'Lifecycle state: DRAFT → PENDING → APPROVED | REJECTED.';


-- ──────────────────────────────────────────────────────────
-- Allocation rule configuration
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS allocation_rule (
    id                  SERIAL       PRIMARY KEY,
    name                VARCHAR(100) NOT NULL,
    description         TEXT,
    source_table        VARCHAR(50)  NOT NULL DEFAULT 'proc_inst_data',
    lookup_table        VARCHAR(50)  NOT NULL DEFAULT 'ref_static_allocation',
    output_table        VARCHAR(50)  NOT NULL DEFAULT 'fct_mgmt_ledger',
    join_key            VARCHAR(50)  NOT NULL DEFAULT 'customer_id',
    filter_json         JSONB,        -- {"logic":"AND","conditions":[...]}
    source_dim_json     JSONB,        -- per-dimension source member filters
    output_dim_json     JSONB,        -- per-dimension output mapping (DEBIT)
    credit_dim_json     JSONB,        -- per-dimension output mapping (CREDIT)
    allocation_method   VARCHAR(20)  NOT NULL DEFAULT 'RATIO',    -- RATIO | DISTRIBUTION | STATIC
    distribution_driver VARCHAR(100),                             -- driver_name for DISTRIBUTION method
    balance_column      VARCHAR(50),                              -- specific balance column to allocate; NULL = all
    entry_mode          VARCHAR(20)  NOT NULL DEFAULT 'BOTH',     -- BOTH | DEBIT_ONLY | CREDIT_ONLY
    generate_offset     BOOLEAN      NOT NULL DEFAULT TRUE,
    offset_account      VARCHAR(50),
    is_active           BOOLEAN      NOT NULL DEFAULT TRUE,
    status              VARCHAR(20)  NOT NULL DEFAULT 'ACTIVE',
    created_by          VARCHAR(50),
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  allocation_rule                     IS 'Configuration for a single allocation rule — source table, lookup, output, method and dimension mappings.';
COMMENT ON COLUMN allocation_rule.allocation_method   IS 'RATIO=ratio from ref_static_allocation, DISTRIBUTION=driver-based, STATIC=1:1 mapping.';
COMMENT ON COLUMN allocation_rule.entry_mode          IS 'BOTH=generate debit+credit, DEBIT_ONLY, CREDIT_ONLY.';
COMMENT ON COLUMN allocation_rule.filter_json         IS 'Optional JSON filter applied to source rows before allocation.';


-- ──────────────────────────────────────────────────────────
-- Single-rule batch run audit
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS batch_run (
    id                VARCHAR(36)   PRIMARY KEY,  -- UUID
    rule_id           INTEGER       NOT NULL REFERENCES allocation_rule(id),
    as_of_date        DATE          NOT NULL,
    status            VARCHAR(20)   NOT NULL DEFAULT 'RUNNING',  -- RUNNING | COMPLETED | FAILED
    source_row_count  INTEGER       NOT NULL DEFAULT 0,
    output_row_count  INTEGER       NOT NULL DEFAULT 0,
    orphan_count      INTEGER       NOT NULL DEFAULT 0,
    source_total      NUMERIC(18,6) NOT NULL DEFAULT 0,
    output_total      NUMERIC(18,6) NOT NULL DEFAULT 0,
    started_at        TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    completed_at      TIMESTAMPTZ,
    run_by            VARCHAR(50)   NOT NULL,
    error_message     TEXT
);

COMMENT ON TABLE batch_run IS 'Audit record for a single allocation rule engine execution.';

CREATE INDEX IF NOT EXISTS ix_batch_run_rule_id    ON batch_run(rule_id);
CREATE INDEX IF NOT EXISTS ix_batch_run_as_of_date ON batch_run(as_of_date);


-- ──────────────────────────────────────────────────────────
-- Multi-task batch definition
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS batch_definition (
    id                INTEGER      PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    name              VARCHAR(100) NOT NULL UNIQUE,
    description       TEXT,
    continue_on_error BOOLEAN      NOT NULL DEFAULT FALSE,
    is_active         BOOLEAN      NOT NULL DEFAULT TRUE,
    created_by        VARCHAR(50),
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  batch_definition                    IS 'Named, ordered sequence of batch tasks (allocation, FTP, data file, custom SP steps).';
COMMENT ON COLUMN batch_definition.continue_on_error  IS 'If TRUE, continue executing subsequent steps even if a step fails.';


-- ──────────────────────────────────────────────────────────
-- Ordered steps within a batch definition
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS batch_task (
    id            INTEGER      PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    definition_id INTEGER      NOT NULL REFERENCES batch_definition(id) ON DELETE CASCADE,
    step_order    INTEGER      NOT NULL DEFAULT 0,
    task_type     VARCHAR(30)  NOT NULL,  -- ALLOCATION | FTP | DATAFILE_IMPORT | DATAFILE_EXPORT | CUSTOM_SP
    ref_id        VARCHAR(100),           -- rule_id | format_id | export_id | sp_name
    label         VARCHAR(200),
    params_json   JSONB                   -- for CUSTOM_SP: {"param": "value", ...}
);

COMMENT ON TABLE  batch_task           IS 'One ordered step within a batch definition.';
COMMENT ON COLUMN batch_task.task_type IS 'Step type: ALLOCATION, FTP, DATAFILE_IMPORT, DATAFILE_EXPORT, CUSTOM_SP.';
COMMENT ON COLUMN batch_task.ref_id    IS 'References the target: allocation rule id, data file format name, or SP name.';
COMMENT ON COLUMN batch_task.params_json IS 'CUSTOM_SP parameters with optional runtime tokens {as_of_date} and {run_by}.';

CREATE INDEX IF NOT EXISTS ix_batch_task_definition_id ON batch_task(definition_id);


-- ──────────────────────────────────────────────────────────
-- Top-level execution record for a batch definition run
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS batch_execution (
    id            VARCHAR(36)  PRIMARY KEY,  -- UUID
    definition_id INTEGER      NOT NULL REFERENCES batch_definition(id),
    as_of_date    DATE         NOT NULL,
    status        VARCHAR(20)  NOT NULL DEFAULT 'RUNNING',  -- RUNNING | COMPLETED | FAILED | PARTIAL
    started_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    completed_at  TIMESTAMPTZ,
    run_by        VARCHAR(50)  NOT NULL,
    error_message TEXT
);

COMMENT ON TABLE  batch_execution        IS 'One execution instance of a batch definition. Parent of all batch_execution_step rows.';
COMMENT ON COLUMN batch_execution.status IS 'COMPLETED=all steps succeeded, FAILED=critical failure, PARTIAL=some steps failed with continue_on_error=TRUE.';

CREATE INDEX IF NOT EXISTS ix_batch_execution_definition_id ON batch_execution(definition_id);
CREATE INDEX IF NOT EXISTS ix_batch_execution_as_of_date    ON batch_execution(as_of_date);


-- ──────────────────────────────────────────────────────────
-- Per-task result row within a batch execution
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS batch_execution_step (
    id            INTEGER      PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    execution_id  VARCHAR(36)  NOT NULL REFERENCES batch_execution(id) ON DELETE CASCADE,
    step_order    INTEGER      NOT NULL,
    task_type     VARCHAR(30)  NOT NULL,
    ref_id        VARCHAR(100),
    params_json   JSONB,       -- copied from batch_task at dispatch time
    label         VARCHAR(200),
    status        VARCHAR(20)  NOT NULL DEFAULT 'PENDING',  -- PENDING | RUNNING | COMPLETED | FAILED | SKIPPED
    ref_run_id    VARCHAR(36), -- ID of the underlying engine run record (batch_run, ftp_run, datafile_batch, sp_run)
    started_at    TIMESTAMPTZ,
    completed_at  TIMESTAMPTZ,
    summary       TEXT,
    error_message TEXT
);

COMMENT ON TABLE  batch_execution_step           IS 'Per-task result row within a batch execution. One row per step per execution.';
COMMENT ON COLUMN batch_execution_step.ref_run_id IS 'FK to the underlying run record created by the engine for this step.';

CREATE INDEX IF NOT EXISTS ix_batch_execution_step_execution_id ON batch_execution_step(execution_id);


-- ──────────────────────────────────────────────────────────
-- Post-approval action log
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS post_approval_log (
    id               INTEGER      PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    upload_batch_id  VARCHAR(36)  NOT NULL REFERENCES upload_batch(id),
    action_type      VARCHAR(20)  NOT NULL,   -- run_rules | stored_procedure
    action_ref       VARCHAR(200),            -- rule ID CSV or procedure name
    status           VARCHAR(20)  NOT NULL,   -- SUCCESS | FAILED | SKIPPED
    detail           TEXT,                    -- summary or error message
    executed_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    executed_by      VARCHAR(50)  NOT NULL
);

COMMENT ON TABLE  post_approval_log             IS 'Logs each automatic action triggered when an upload batch is approved by the checker.';
COMMENT ON COLUMN post_approval_log.action_type IS 'run_rules=allocation engine, stored_procedure=custom SP.';

CREATE INDEX IF NOT EXISTS ix_post_approval_log_upload_batch_id ON post_approval_log(upload_batch_id);


-- ──────────────────────────────────────────────────────────
-- Stored-procedure invocation audit
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sp_run (
    id             VARCHAR(36)  PRIMARY KEY,  -- UUID
    sp_name        VARCHAR(200) NOT NULL,
    params_json    JSONB,
    status         VARCHAR(20)  NOT NULL DEFAULT 'RUNNING',  -- RUNNING | COMPLETED | FAILED
    started_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    completed_at   TIMESTAMPTZ,
    run_by         VARCHAR(50),
    result_message TEXT,
    error_message  TEXT,
    exec_step_id   INTEGER      REFERENCES batch_execution_step(id)
);

COMMENT ON TABLE  sp_run              IS 'Audit record for each stored-procedure call made from a CUSTOM_SP batch step.';
COMMENT ON COLUMN sp_run.exec_step_id IS 'Links back to the batch_execution_step that triggered this SP run.';
COMMENT ON COLUMN sp_run.params_json  IS 'Resolved parameter values actually passed to the SP (after token substitution).';

CREATE INDEX IF NOT EXISTS ix_sp_run_exec_step_id ON sp_run(exec_step_id);
