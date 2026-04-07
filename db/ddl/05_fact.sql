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
