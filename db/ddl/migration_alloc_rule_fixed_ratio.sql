-- Migration: Add fixed_ratio column to allocation_rule
ALTER TABLE allocation_rule ADD COLUMN fixed_ratio NUMERIC(10, 6);

COMMENT ON COLUMN allocation_rule.fixed_ratio IS 'Fixed ratio to apply for STATIC allocation method. Defaults to 1.0 if NULL.';
