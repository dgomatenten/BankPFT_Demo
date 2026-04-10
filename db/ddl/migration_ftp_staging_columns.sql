-- ============================================================
-- migration_ftp_staging_columns.sql
-- Injects LP and CLP components natively into the staging 
-- instrument tables to support the newly refactored FTP engine.
-- ============================================================

ALTER TABLE stg_inst_data 
    ADD COLUMN IF NOT EXISTS lp_rate NUMERIC(18,6),
    ADD COLUMN IF NOT EXISTS lp_amount NUMERIC(18,6),
    ADD COLUMN IF NOT EXISTS clp_rate NUMERIC(18,6),
    ADD COLUMN IF NOT EXISTS clp_amount NUMERIC(18,6);

ALTER TABLE proc_inst_data 
    ADD COLUMN IF NOT EXISTS lp_rate NUMERIC(18,6),
    ADD COLUMN IF NOT EXISTS lp_amount NUMERIC(18,6),
    ADD COLUMN IF NOT EXISTS clp_rate NUMERIC(18,6),
    ADD COLUMN IF NOT EXISTS clp_amount NUMERIC(18,6);

COMMENT ON COLUMN proc_inst_data.lp_rate IS 'Liquidity Premium rate assigned by the FTP model.';
COMMENT ON COLUMN proc_inst_data.lp_amount IS 'Liquidity Premium calculated output (balance * lp_rate * fraction).';
COMMENT ON COLUMN proc_inst_data.clp_rate IS 'Contingent Liquidity Premium rate assigned by the FTP model.';
COMMENT ON COLUMN proc_inst_data.clp_amount IS 'Contingent Liquidity Premium calculated output (balance * clp_rate * fraction).';
