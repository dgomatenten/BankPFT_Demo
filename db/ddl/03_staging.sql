-- ============================================================
-- 03_staging.sql  —  Instrument & GL Staging / Processing Tables
-- Tables: stg_inst_data, proc_inst_data, stg_gl_data, proc_gl_data
--
-- stg_*   : raw rows as uploaded by the user (not yet approved)
-- proc_*  : maker/checker-approved rows used by the allocation engine
-- ============================================================

-- ──────────────────────────────────────────────────────────
-- Instrument staging (raw upload)
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS stg_inst_data (
    id              SERIAL        PRIMARY KEY,
    upload_batch_id VARCHAR(36)   NOT NULL,
    as_of_date      DATE          NOT NULL,
    transaction_number VARCHAR(100),
    account_id      VARCHAR(20)   NOT NULL,
    customer_id     VARCHAR(20)   NOT NULL,
    product_code    VARCHAR(20)   NOT NULL,
    org_unit_id     VARCHAR(20)   NOT NULL,
    balance         NUMERIC(18,6) NOT NULL,
    interest_income NUMERIC(18,6) NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE stg_inst_data IS 'Raw instrument-level data as uploaded — pending maker/checker approval.';

CREATE INDEX IF NOT EXISTS ix_stg_inst_data_upload_batch_id ON stg_inst_data(upload_batch_id);
CREATE INDEX IF NOT EXISTS ix_stg_inst_data_as_of_date      ON stg_inst_data(as_of_date);


-- ──────────────────────────────────────────────────────────
-- Instrument processing (approved data used by engines)
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS proc_inst_data (
    id              SERIAL        PRIMARY KEY,
    upload_batch_id VARCHAR(36)   NOT NULL,
    as_of_date      DATE          NOT NULL,
    transaction_number VARCHAR(100),
    account_id      VARCHAR(20)   NOT NULL,
    customer_id     VARCHAR(20)   NOT NULL,
    product_code    VARCHAR(20)   NOT NULL,
    org_unit_id     VARCHAR(20)   NOT NULL,
    balance         NUMERIC(18,6) NOT NULL,
    interest_income NUMERIC(18,6) NOT NULL DEFAULT 0,
    base_rate       NUMERIC(18,6),           -- populated by FTP engine
    cost_of_fund    NUMERIC(18,6),           -- populated by FTP engine (balance × rate × day fraction)
    validated_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  proc_inst_data              IS 'Approved instrument data consumed by allocation and FTP engines.';
COMMENT ON COLUMN proc_inst_data.base_rate    IS 'Moving-average transfer rate assigned by the FTP engine.';
COMMENT ON COLUMN proc_inst_data.cost_of_fund IS 'Funds-transfer cost: balance × base_rate × actual/actual day fraction.';

CREATE INDEX IF NOT EXISTS ix_proc_inst_data_upload_batch_id ON proc_inst_data(upload_batch_id);
CREATE INDEX IF NOT EXISTS ix_proc_inst_data_as_of_date      ON proc_inst_data(as_of_date);


-- ──────────────────────────────────────────────────────────
-- GL staging (raw upload)
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS stg_gl_data (
    id              SERIAL        PRIMARY KEY,
    upload_batch_id VARCHAR(36)   NOT NULL,
    as_of_date      DATE          NOT NULL,
    gl_account      VARCHAR(20)   NOT NULL,
    org_unit_id     VARCHAR(20)   NOT NULL,
    debit           NUMERIC(18,6) NOT NULL DEFAULT 0,
    credit          NUMERIC(18,6) NOT NULL DEFAULT 0,
    balance         NUMERIC(18,6) NOT NULL,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE stg_gl_data IS 'Raw general-ledger balances as uploaded — pending maker/checker approval.';

CREATE INDEX IF NOT EXISTS ix_stg_gl_data_upload_batch_id ON stg_gl_data(upload_batch_id);
CREATE INDEX IF NOT EXISTS ix_stg_gl_data_as_of_date      ON stg_gl_data(as_of_date);


-- ──────────────────────────────────────────────────────────
-- GL processing (approved data)
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS proc_gl_data (
    id              SERIAL        PRIMARY KEY,
    upload_batch_id VARCHAR(36)   NOT NULL,
    as_of_date      DATE          NOT NULL,
    gl_account      VARCHAR(20)   NOT NULL,
    org_unit_id     VARCHAR(20)   NOT NULL,
    debit           NUMERIC(18,6) NOT NULL DEFAULT 0,
    credit          NUMERIC(18,6) NOT NULL DEFAULT 0,
    balance         NUMERIC(18,6) NOT NULL,
    validated_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE proc_gl_data IS 'Approved GL balances consumed by the allocation engine.';

CREATE INDEX IF NOT EXISTS ix_proc_gl_data_upload_batch_id ON proc_gl_data(upload_batch_id);
CREATE INDEX IF NOT EXISTS ix_proc_gl_data_as_of_date      ON proc_gl_data(as_of_date);
