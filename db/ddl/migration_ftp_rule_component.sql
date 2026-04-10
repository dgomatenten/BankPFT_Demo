-- ============================================================
-- migration_ftp_rule_component.sql
-- Adds component column to ftp_model_rule (COF / LP / CLP)
-- and drops the old lp_rate / clp_rate scalar columns.
--
-- After this migration each rule targets one specific FTP
-- output component, with its own independent rate curve.
-- ============================================================

ALTER TABLE ftp_model_rule
    ADD COLUMN IF NOT EXISTS component VARCHAR(3) NOT NULL DEFAULT 'COF';

COMMENT ON COLUMN ftp_model_rule.component IS
    'FTP output component this rule computes: COF (Cost of Funds), LP (Liquidity Premium), CLP (Contingent Liquidity Premium).';

-- Drop old scalar rate columns — each component now has its own rule + rate lookup.
ALTER TABLE ftp_model_rule DROP COLUMN IF EXISTS lp_rate;
ALTER TABLE ftp_model_rule DROP COLUMN IF EXISTS clp_rate;
