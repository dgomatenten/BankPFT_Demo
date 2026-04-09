-- ============================================================
-- Migration: TEXT → JSONB columns + add as_of_date + balance_column
-- Run against an EXISTING PostgreSQL bankpft database.
-- Safe to re-run (uses IF NOT EXISTS / USING for idempotency).
-- ============================================================

BEGIN;

-- ──────────────────────────────────────────────────────────
-- 1. allocation_rule: TEXT → JSONB (convert existing data)
-- ──────────────────────────────────────────────────────────
ALTER TABLE allocation_rule
    ALTER COLUMN filter_json      TYPE JSONB USING filter_json::jsonb,
    ALTER COLUMN source_dim_json  TYPE JSONB USING source_dim_json::jsonb,
    ALTER COLUMN output_dim_json  TYPE JSONB USING output_dim_json::jsonb,
    ALTER COLUMN credit_dim_json  TYPE JSONB USING credit_dim_json::jsonb;

-- 2. allocation_rule: add balance_column if missing
ALTER TABLE allocation_rule
    ADD COLUMN IF NOT EXISTS balance_column VARCHAR(50);

-- ──────────────────────────────────────────────────────────
-- 3. Lookup tables: add as_of_date column + index
-- ──────────────────────────────────────────────────────────

-- ref_static_allocation
ALTER TABLE ref_static_allocation
    ADD COLUMN IF NOT EXISTS as_of_date DATE;
CREATE INDEX IF NOT EXISTS ix_ref_static_allocation_as_of_date
    ON ref_static_allocation(as_of_date);

-- ref_org_reclass
ALTER TABLE ref_org_reclass
    ADD COLUMN IF NOT EXISTS as_of_date DATE;
CREATE INDEX IF NOT EXISTS ix_ref_org_reclass_as_of_date
    ON ref_org_reclass(as_of_date);

-- ref_static_distribution
ALTER TABLE ref_static_distribution
    ADD COLUMN IF NOT EXISTS as_of_date DATE;
CREATE INDEX IF NOT EXISTS ix_ref_static_distribution_as_of_date
    ON ref_static_distribution(as_of_date);

-- ref_static_alloc
ALTER TABLE ref_static_alloc
    ADD COLUMN IF NOT EXISTS as_of_date DATE;
CREATE INDEX IF NOT EXISTS ix_ref_static_alloc_as_of_date
    ON ref_static_alloc(as_of_date);

COMMIT;

-- ──────────────────────────────────────────────────────────
-- Verify
-- ──────────────────────────────────────────────────────────
SELECT table_name, column_name, data_type
  FROM information_schema.columns
 WHERE table_name IN (
         'allocation_rule',
         'ref_static_allocation', 'ref_org_reclass',
         'ref_static_distribution', 'ref_static_alloc'
       )
   AND column_name IN (
         'filter_json', 'source_dim_json', 'output_dim_json', 'credit_dim_json',
         'balance_column', 'as_of_date'
       )
 ORDER BY table_name, column_name;
