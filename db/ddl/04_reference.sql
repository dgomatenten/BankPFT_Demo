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
