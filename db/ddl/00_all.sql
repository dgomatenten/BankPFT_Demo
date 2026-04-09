-- ============================================================
-- 00_all.sql  —  Master DDL: All Tables in Dependency Order
-- Run with:  psql $DATABASE_URL -f db/ddl/00_all.sql
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- gen_random_uuid()

-- ────────────────────────────────────────────────────────────
-- 1. Authentication & User Management (no FK dependencies)
-- ────────────────────────────────────────────────────────────
-- ============================================================
-- 01_auth.sql  —  Authentication & User Management
-- Tables: "group", "user", user_group
--
-- Note: "group" and "user" are reserved words in PostgreSQL and
-- must be quoted everywhere they appear.
-- ============================================================

CREATE TABLE IF NOT EXISTS "group" (
    id          SERIAL        PRIMARY KEY,
    name        VARCHAR(80)   NOT NULL UNIQUE,
    description VARCHAR(200),
    can_make    BOOLEAN       NOT NULL DEFAULT FALSE,
    can_check   BOOLEAN       NOT NULL DEFAULT FALSE,
    is_admin    BOOLEAN       NOT NULL DEFAULT FALSE,
    is_active   BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  "group"             IS 'Application permission groups (Maker / Checker / Admin).';
COMMENT ON COLUMN "group".can_make    IS 'Members of this group may submit (make) upload batches.';
COMMENT ON COLUMN "group".can_check   IS 'Members of this group may approve/reject (check) upload batches.';
COMMENT ON COLUMN "group".is_admin    IS 'Members of this group have full administrative access.';


CREATE TABLE IF NOT EXISTS "user" (
    id            SERIAL        PRIMARY KEY,
    username      VARCHAR(80)   NOT NULL UNIQUE,
    display_name  VARCHAR(120),
    password_hash VARCHAR(256)  NOT NULL,
    is_active     BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  "user"              IS 'Application users. Passwords stored as Werkzeug pbkdf2 hashes.';
COMMENT ON COLUMN "user".password_hash IS 'Werkzeug generate_password_hash output — never store plain text.';


CREATE TABLE IF NOT EXISTS user_group (
    user_id  INTEGER NOT NULL REFERENCES "user"("id")  ON DELETE CASCADE,
    group_id INTEGER NOT NULL REFERENCES "group"("id") ON DELETE CASCADE,
    PRIMARY KEY (user_id, group_id)
);

COMMENT ON TABLE user_group IS 'Many-to-many join between users and permission groups.';

-- ────────────────────────────────────────────────────────────
-- 2. Dimension / Master Data (no FK dependencies)
-- ────────────────────────────────────────────────────────────
-- ============================================================
-- 02_dimensions.sql  —  Dimension / Master Data Tables
-- Tables: dim_org_unit, dim_product, dim_customer, dim_account
-- ============================================================

CREATE TABLE IF NOT EXISTS dim_org_unit (
    org_unit_id VARCHAR(20)  PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    parent_id   VARCHAR(20)  REFERENCES dim_org_unit(org_unit_id),
    is_leaf     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  dim_org_unit           IS 'Organisational unit hierarchy (branches, divisions, cost centres).';
COMMENT ON COLUMN dim_org_unit.parent_id IS 'Self-referencing FK to build the org tree. NULL for root nodes.';
COMMENT ON COLUMN dim_org_unit.is_leaf   IS 'TRUE if this node has no children (used by allocation engine).';


CREATE TABLE IF NOT EXISTS dim_product (
    product_code VARCHAR(20)  PRIMARY KEY,
    name         VARCHAR(100) NOT NULL,
    category     VARCHAR(50),
    is_leaf      BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE dim_product IS 'Product dimension — loans, deposits, fee products, etc.';


CREATE TABLE IF NOT EXISTS dim_customer (
    customer_id VARCHAR(20)  PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    segment     VARCHAR(50),
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE dim_customer IS 'Customer dimension — individual or corporate customers.';


CREATE TABLE IF NOT EXISTS dim_account (
    account_id   VARCHAR(20)  PRIMARY KEY,
    customer_id  VARCHAR(20)  NOT NULL REFERENCES dim_customer(customer_id),
    product_code VARCHAR(20)  NOT NULL REFERENCES dim_product(product_code),
    org_unit_id  VARCHAR(20)  NOT NULL REFERENCES dim_org_unit(org_unit_id),
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE dim_account IS 'Account dimension — the intersection of customer, product, and org unit.';

-- Indexes for FK join performance
CREATE INDEX IF NOT EXISTS ix_dim_account_customer_id  ON dim_account(customer_id);
CREATE INDEX IF NOT EXISTS ix_dim_account_product_code ON dim_account(product_code);
CREATE INDEX IF NOT EXISTS ix_dim_account_org_unit_id  ON dim_account(org_unit_id);

-- ────────────────────────────────────────────────────────────
-- 3. Staging & Processing (refs upload_batch_id by value)
-- ────────────────────────────────────────────────────────────
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

-- ────────────────────────────────────────────────────────────
-- 4. Reference / Allocation Input (depends on dim_*)
-- ────────────────────────────────────────────────────────────
-- ============================================================
-- 04_reference.sql  —  Allocation Reference / Input Tables
-- Tables: ref_static_allocation, ref_org_reclass,
--         ref_static_distribution, ref_static_alloc
--
-- All tables use MakerCheckerMixin columns:
--   status, maker_id, checker_id, created_at, updated_at
-- Status lifecycle: DRAFT → PENDING → APPROVED | REJECTED
-- ============================================================

-- ──────────────────────────────────────────────────────────
-- Static allocation ratios (Ratio-Based allocation method)
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ref_static_allocation (
    id                  SERIAL        PRIMARY KEY,
    upload_batch_id     VARCHAR(36),
    allocation_id       VARCHAR(36)   NOT NULL,
    customer_id         VARCHAR(20)   NOT NULL REFERENCES dim_customer(customer_id),
    source_org_unit_id  VARCHAR(20)   NOT NULL REFERENCES dim_org_unit(org_unit_id),
    target_org_unit_id  VARCHAR(20)   NOT NULL REFERENCES dim_org_unit(org_unit_id),
    ratio               NUMERIC(10,6) NOT NULL,
    comments            TEXT,
    -- MakerCheckerMixin
    status              VARCHAR(20)   NOT NULL DEFAULT 'DRAFT',
    maker_id            VARCHAR(50)   NOT NULL,
    checker_id          VARCHAR(50),
    created_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  ref_static_allocation            IS 'Customer-level allocation ratios used by the Ratio-Based allocation method.';
COMMENT ON COLUMN ref_static_allocation.allocation_id IS 'Groups rows that belong to the same allocation set.';
COMMENT ON COLUMN ref_static_allocation.ratio      IS 'Decimal ratio (e.g. 0.40 = 40 %). Rows per allocation_id should sum to 1.';

CREATE INDEX IF NOT EXISTS ix_ref_static_allocation_upload_batch_id ON ref_static_allocation(upload_batch_id);
CREATE INDEX IF NOT EXISTS ix_ref_static_allocation_allocation_id   ON ref_static_allocation(allocation_id);


-- ──────────────────────────────────────────────────────────
-- Org unit reclassification mapping
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ref_org_reclass (
    id                  SERIAL        PRIMARY KEY,
    upload_batch_id     VARCHAR(36),
    reclass_id          VARCHAR(36)   NOT NULL,
    source_org_unit_id  VARCHAR(20)   NOT NULL REFERENCES dim_org_unit(org_unit_id),
    target_org_unit_id  VARCHAR(20)   NOT NULL REFERENCES dim_org_unit(org_unit_id),
    ratio               NUMERIC(10,6) NOT NULL DEFAULT 1.0,
    comments            TEXT,
    -- MakerCheckerMixin
    status              VARCHAR(20)   NOT NULL DEFAULT 'DRAFT',
    maker_id            VARCHAR(50)   NOT NULL,
    checker_id          VARCHAR(50),
    created_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  ref_org_reclass         IS 'Org unit reclassification mappings — restructures org positions across periods.';
COMMENT ON COLUMN ref_org_reclass.ratio   IS 'Typically 1.0 for full movement; fractional for partial transfers.';

CREATE INDEX IF NOT EXISTS ix_ref_org_reclass_upload_batch_id ON ref_org_reclass(upload_batch_id);
CREATE INDEX IF NOT EXISTS ix_ref_org_reclass_reclass_id      ON ref_org_reclass(reclass_id);


-- ──────────────────────────────────────────────────────────
-- Static distribution ratios (Distribution allocation method)
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ref_static_distribution (
    id              SERIAL        PRIMARY KEY,
    upload_batch_id VARCHAR(36),
    driver_name     VARCHAR(100)  NOT NULL DEFAULT '',
    distribution_id VARCHAR(50)   NOT NULL,
    -- Source join columns — populate the one matching the rule's join_key
    customer_id     VARCHAR(20),
    org_unit_id     VARCHAR(20),
    product_code    VARCHAR(20),
    -- Target
    target_dim      VARCHAR(50)   NOT NULL,
    ratio           NUMERIC(10,6) NOT NULL,
    comments        TEXT,
    -- MakerCheckerMixin
    status          VARCHAR(20)   NOT NULL DEFAULT 'DRAFT',
    maker_id        VARCHAR(50)   NOT NULL,
    checker_id      VARCHAR(50),
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  ref_static_distribution              IS 'Distribution table for the Static Distribution allocation method.';
COMMENT ON COLUMN ref_static_distribution.driver_name IS 'Groups rows into named distribution drivers referenced by allocation rules.';
COMMENT ON COLUMN ref_static_distribution.distribution_id IS 'Groups rows within a driver that share a source value. Ratios should sum to 1.';
COMMENT ON COLUMN ref_static_distribution.target_dim  IS 'Target dimension value (e.g. org_unit_id) after distribution.';

CREATE INDEX IF NOT EXISTS ix_ref_static_distribution_upload_batch_id ON ref_static_distribution(upload_batch_id);
CREATE INDEX IF NOT EXISTS ix_ref_static_distribution_driver_name     ON ref_static_distribution(driver_name);
CREATE INDEX IF NOT EXISTS ix_ref_static_distribution_distribution_id ON ref_static_distribution(distribution_id);
CREATE INDEX IF NOT EXISTS ix_ref_static_distribution_customer_id     ON ref_static_distribution(customer_id);
CREATE INDEX IF NOT EXISTS ix_ref_static_distribution_org_unit_id     ON ref_static_distribution(org_unit_id);
CREATE INDEX IF NOT EXISTS ix_ref_static_distribution_product_code    ON ref_static_distribution(product_code);


-- ──────────────────────────────────────────────────────────
-- Static allocation mapping (Static Allocation method)
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ref_static_alloc (
    id              SERIAL        PRIMARY KEY,
    upload_batch_id VARCHAR(36),
    alloc_id        VARCHAR(50)   NOT NULL,
    -- Source join columns — populate the one matching the rule's join_key
    customer_id     VARCHAR(20),
    org_unit_id     VARCHAR(20),
    product_code    VARCHAR(20),
    -- Target
    target_dim      VARCHAR(50)   NOT NULL,
    ratio           NUMERIC(10,6) NOT NULL DEFAULT 1.0,
    comments        TEXT,
    -- MakerCheckerMixin
    status          VARCHAR(20)   NOT NULL DEFAULT 'DRAFT',
    maker_id        VARCHAR(50)   NOT NULL,
    checker_id      VARCHAR(50),
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  ref_static_alloc         IS '1:1 source-to-target mapping for the Static Allocation method. No splitting; ratio defaults to 1.0.';
COMMENT ON COLUMN ref_static_alloc.alloc_id IS 'Allocation set identifier referenced by the allocation rule.';

CREATE INDEX IF NOT EXISTS ix_ref_static_alloc_upload_batch_id ON ref_static_alloc(upload_batch_id);
CREATE INDEX IF NOT EXISTS ix_ref_static_alloc_alloc_id        ON ref_static_alloc(alloc_id);
CREATE INDEX IF NOT EXISTS ix_ref_static_alloc_customer_id     ON ref_static_alloc(customer_id);
CREATE INDEX IF NOT EXISTS ix_ref_static_alloc_org_unit_id     ON ref_static_alloc(org_unit_id);
CREATE INDEX IF NOT EXISTS ix_ref_static_alloc_product_code    ON ref_static_alloc(product_code);

-- ────────────────────────────────────────────────────────────
-- 5. Fact / Output Tables (depends on batch_run via runtime)
-- ────────────────────────────────────────────────────────────
-- ============================================================
-- 05_fact.sql  —  Allocation Output / Fact Tables
-- Tables: fct_mgmt_ledger, fct_mgmt_instrument
--
-- Written by the allocation engine after each batch run.
-- One row per source account per DEBIT / CREDIT entry.
-- ============================================================

-- ──────────────────────────────────────────────────────────
-- GL-level allocation output
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fct_mgmt_ledger (
    id                  SERIAL        PRIMARY KEY,
    batch_run_id        VARCHAR(36)   NOT NULL,
    as_of_date          DATE          NOT NULL,
    entry_type          VARCHAR(10)   NOT NULL DEFAULT 'DEBIT',  -- DEBIT | CREDIT
    allocation_id       VARCHAR(36),
    source_account_id   VARCHAR(20)   NOT NULL,
    customer_id         VARCHAR(20)   NOT NULL,
    product_code        VARCHAR(20)   NOT NULL,
    source_org_unit_id  VARCHAR(20)   NOT NULL,
    target_org_unit_id  VARCHAR(20)   NOT NULL,
    source_balance      NUMERIC(18,6) NOT NULL,
    allocated_balance   NUMERIC(18,6) NOT NULL,
    allocated_income    NUMERIC(18,6) NOT NULL DEFAULT 0,
    ratio_applied       NUMERIC(10,6) NOT NULL,
    is_orphan           BOOLEAN       NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  fct_mgmt_ledger              IS 'GL-level management ledger output produced by the allocation engine.';
COMMENT ON COLUMN fct_mgmt_ledger.entry_type   IS 'DEBIT or CREDIT — every balance movement generates matching entries.';
COMMENT ON COLUMN fct_mgmt_ledger.is_orphan    IS 'TRUE when the source row had no matching lookup ratio (balance carried at ratio 1.0 to prevent data loss).';
COMMENT ON COLUMN fct_mgmt_ledger.batch_run_id IS 'Links to batch_run.id — all rows for a single engine execution share this ID.';

CREATE INDEX IF NOT EXISTS ix_fct_mgmt_ledger_batch_run_id ON fct_mgmt_ledger(batch_run_id);
CREATE INDEX IF NOT EXISTS ix_fct_mgmt_ledger_as_of_date   ON fct_mgmt_ledger(as_of_date);


-- ──────────────────────────────────────────────────────────
-- Instrument-level allocation output
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fct_mgmt_instrument (
    id                  SERIAL        PRIMARY KEY,
    batch_run_id        VARCHAR(36)   NOT NULL,
    as_of_date          DATE          NOT NULL,
    transaction_number  VARCHAR(100),
    entry_type          VARCHAR(10)   NOT NULL DEFAULT 'DEBIT',  -- DEBIT | CREDIT
    allocation_id       VARCHAR(36),
    source_account_id   VARCHAR(20)   NOT NULL,
    customer_id         VARCHAR(20)   NOT NULL,
    product_code        VARCHAR(20)   NOT NULL,
    source_org_unit_id  VARCHAR(20)   NOT NULL,
    target_org_unit_id  VARCHAR(20)   NOT NULL,
    source_balance      NUMERIC(18,6) NOT NULL,
    allocated_balance   NUMERIC(18,6) NOT NULL,
    allocated_income    NUMERIC(18,6) NOT NULL DEFAULT 0,
    ratio_applied       NUMERIC(10,6) NOT NULL,
    is_orphan           BOOLEAN       NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  fct_mgmt_instrument            IS 'Instrument-level management output — mirrors fct_mgmt_ledger at account granularity.';
COMMENT ON COLUMN fct_mgmt_instrument.is_orphan  IS 'TRUE when the source account had no matching lookup ratio.';

CREATE INDEX IF NOT EXISTS ix_fct_mgmt_instrument_batch_run_id ON fct_mgmt_instrument(batch_run_id);
CREATE INDEX IF NOT EXISTS ix_fct_mgmt_instrument_as_of_date   ON fct_mgmt_instrument(as_of_date);

-- ────────────────────────────────────────────────────────────
-- 6. Fund Transfer Pricing (ftp_product_config depends on dim_product)
-- ────────────────────────────────────────────────────────────
-- ============================================================
-- 06_ftp.sql  —  Fund Transfer Pricing Tables
-- Tables: ref_interest_rate, ftp_product_config, ftp_run
-- ============================================================

-- ──────────────────────────────────────────────────────────
-- Interest rate curves (uploaded via Maker/Checker workflow)
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ref_interest_rate (
    id                   SERIAL        PRIMARY KEY,
    upload_batch_id      VARCHAR(36),
    effective_date       DATE          NOT NULL,
    interest_rate_code   VARCHAR(20)   NOT NULL,
    term                 INTEGER       NOT NULL,           -- numeric tenor value
    term_mult            VARCHAR(1)    NOT NULL,           -- D=day  M=month  Y=year
    rate                 NUMERIC(10,6) NOT NULL,           -- decimal, e.g. 0.05 = 5 %
    -- MakerCheckerMixin
    status               VARCHAR(20)   NOT NULL DEFAULT 'DRAFT',
    maker_id             VARCHAR(50)   NOT NULL,
    checker_id           VARCHAR(50),
    created_at           TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  ref_interest_rate                  IS 'Interest rate curve data used by the FTP moving-average engine.';
COMMENT ON COLUMN ref_interest_rate.interest_rate_code IS 'Rate curve identifier (e.g. SOFR, LIBOR, BBR). Must match ftp_product_config.rate_code.';
COMMENT ON COLUMN ref_interest_rate.term             IS 'Numeric tenor (e.g. 3 for a 3-month rate).';
COMMENT ON COLUMN ref_interest_rate.term_mult        IS 'Tenor multiplier: D = days, M = months, Y = years.';
COMMENT ON COLUMN ref_interest_rate.rate             IS 'Rate as a decimal fraction (0.05 = 5 %). Not a percentage.';

CREATE INDEX IF NOT EXISTS ix_ref_interest_rate_upload_batch_id    ON ref_interest_rate(upload_batch_id);
CREATE INDEX IF NOT EXISTS ix_ref_interest_rate_effective_date     ON ref_interest_rate(effective_date);
CREATE INDEX IF NOT EXISTS ix_ref_interest_rate_interest_rate_code ON ref_interest_rate(interest_rate_code);


-- ──────────────────────────────────────────────────────────
-- FTP calculation configuration per product
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ftp_product_config (
    id               SERIAL       PRIMARY KEY,
    product_code     VARCHAR(20)  NOT NULL UNIQUE REFERENCES dim_product(product_code),
    method           VARCHAR(20)  NOT NULL DEFAULT 'MOVING_AVG',  -- MOVING_AVG
    rate_code        VARCHAR(20)  NOT NULL,
    term             INTEGER      NOT NULL,
    term_mult        VARCHAR(1)   NOT NULL,                        -- D, M, Y
    avg_period       INTEGER      NOT NULL DEFAULT 1,
    avg_period_mult  VARCHAR(1)   NOT NULL DEFAULT 'M',            -- D, M, Y
    is_active        BOOLEAN      NOT NULL DEFAULT TRUE,
    created_by       VARCHAR(50),
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  ftp_product_config                IS 'FTP method and rate parameters per product code.';
COMMENT ON COLUMN ftp_product_config.method         IS 'Calculation method. Currently only MOVING_AVG is supported.';
COMMENT ON COLUMN ftp_product_config.avg_period     IS 'Moving-average lookback window length.';
COMMENT ON COLUMN ftp_product_config.avg_period_mult IS 'Lookback window unit: D=days, M=months, Y=years.';


-- ──────────────────────────────────────────────────────────
-- FTP run audit (one row per engine execution)
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ftp_run (
    id                     VARCHAR(36)  PRIMARY KEY,  -- UUID
    as_of_date             DATE         NOT NULL,
    status                 VARCHAR(20)  NOT NULL DEFAULT 'RUNNING',  -- RUNNING | COMPLETED | FAILED
    run_by                 VARCHAR(50),
    instruments_processed  INTEGER      NOT NULL DEFAULT 0,
    instruments_matched    INTEGER      NOT NULL DEFAULT 0,
    instruments_skipped    INTEGER      NOT NULL DEFAULT 0,
    started_at             TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    completed_at           TIMESTAMPTZ,
    error_message          TEXT
);

COMMENT ON TABLE  ftp_run                         IS 'Tracks each FTP engine execution — one row per batch run.';
COMMENT ON COLUMN ftp_run.instruments_matched     IS 'Instruments that had a matching FTP product config and rate.';
COMMENT ON COLUMN ftp_run.instruments_skipped     IS 'Instruments skipped due to missing product config or rate data.';

-- ────────────────────────────────────────────────────────────
-- 7. Workflow — Batches, Allocations, Executions, SPs
--    (upstream: dim_*, then internal FK chain)
-- ────────────────────────────────────────────────────────────
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
    filter_json         TEXT,        -- JSON: {"logic":"AND","conditions":[...]}
    source_dim_json     TEXT,        -- per-dimension source member filters
    output_dim_json     TEXT,        -- per-dimension output mapping (DEBIT)
    credit_dim_json     TEXT,        -- per-dimension output mapping (CREDIT)
    allocation_method   VARCHAR(20)  NOT NULL DEFAULT 'RATIO',    -- RATIO | DISTRIBUTION | STATIC
    distribution_driver VARCHAR(100),                             -- driver_name for DISTRIBUTION method
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

-- ────────────────────────────────────────────────────────────
-- 8. Data File Ingestion / Export
-- ────────────────────────────────────────────────────────────
-- ============================================================
-- 08_datafile.sql  —  Data File Import / Export Audit Table
-- Tables: datafile_batch
-- ============================================================

CREATE TABLE IF NOT EXISTS datafile_batch (
    id            VARCHAR(36)  PRIMARY KEY,  -- UUID
    operation     VARCHAR(10)  NOT NULL,      -- IMPORT | EXPORT
    format_id     VARCHAR(50)  NOT NULL,      -- key from datafile_config.json
    format_name   VARCHAR(100),
    filename      VARCHAR(255) NOT NULL,
    target_table  VARCHAR(50),               -- destination table name (imports only)
    status        VARCHAR(20)  NOT NULL DEFAULT 'RUNNING',  -- RUNNING | COMPLETED | FAILED
    row_count     INTEGER      NOT NULL DEFAULT 0,
    error_count   INTEGER      NOT NULL DEFAULT 0,
    errors_json   JSONB,                     -- JSON list of per-row error strings
    run_by        VARCHAR(50)  NOT NULL,
    started_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    completed_at  TIMESTAMPTZ,
    error_message TEXT
);

COMMENT ON TABLE  datafile_batch              IS 'Audit record for each data file import or export operation.';
COMMENT ON COLUMN datafile_batch.operation    IS 'IMPORT = fixed-length/delimited file loaded into a target table. EXPORT = data written to output file.';
COMMENT ON COLUMN datafile_batch.format_id    IS 'Matches the format key in datafile_config.json (e.g. import_loan, export_inst_proc).';
COMMENT ON COLUMN datafile_batch.target_table IS 'Destination database table for IMPORT operations (NULL for EXPORT).';

CREATE INDEX IF NOT EXISTS ix_datafile_batch_format_id  ON datafile_batch(format_id);
CREATE INDEX IF NOT EXISTS ix_datafile_batch_started_at ON datafile_batch(started_at);

-- ────────────────────────────────────────────────────────────
-- 9. In-App Test Suite (no FK dependencies)
-- ────────────────────────────────────────────────────────────
-- ============================================================
-- 09_test.sql  —  In-App Test Suite Run Table
-- Tables: test_suite_run
-- ============================================================

CREATE TABLE IF NOT EXISTS test_suite_run (
    id           VARCHAR(36)   PRIMARY KEY,  -- UUID
    started_at   TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    triggered_by VARCHAR(50),
    -- Overall result
    status       VARCHAR(10)   NOT NULL DEFAULT 'RUNNING',  -- RUNNING | PASS | FAIL | ERROR
    total        INTEGER       NOT NULL DEFAULT 0,
    passed       INTEGER       NOT NULL DEFAULT 0,
    failed       INTEGER       NOT NULL DEFAULT 0,
    error        INTEGER       NOT NULL DEFAULT 0,
    skipped      INTEGER       NOT NULL DEFAULT 0,
    duration_s   NUMERIC(10,3) NOT NULL DEFAULT 0,
    -- Full pytest-json-report payload and captured stdout
    results_json JSONB,
    stdout       TEXT
);

COMMENT ON TABLE  test_suite_run             IS 'Records each in-app pytest invocation triggered from the /tests/ UI or API.';
COMMENT ON COLUMN test_suite_run.status      IS 'RUNNING while executing. PASS if all tests passed. FAIL if any test failed. ERROR on pytest crash.';
COMMENT ON COLUMN test_suite_run.results_json IS 'Full pytest-json-report output — individual test results, durations, and error traces.';
