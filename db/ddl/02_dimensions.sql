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
