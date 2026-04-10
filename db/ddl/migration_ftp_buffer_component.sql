-- ============================================================
-- migration_ftp_buffer_component.sql
-- Adds Buffer Asset Cost (BUF) columns to instrument tables.
-- ============================================================

ALTER TABLE stg_inst_data 
    ADD COLUMN IF NOT EXISTS buffer_rate NUMERIC(18,6),
    ADD COLUMN IF NOT EXISTS buffer_amount NUMERIC(18,6);

ALTER TABLE proc_inst_data 
    ADD COLUMN IF NOT EXISTS buffer_rate NUMERIC(18,6),
    ADD COLUMN IF NOT EXISTS buffer_amount NUMERIC(18,6);

COMMENT ON COLUMN proc_inst_data.buffer_rate IS 'Buffer Asset Cost rate assigned by the FTP model.';
COMMENT ON COLUMN proc_inst_data.buffer_amount IS 'Buffer Asset Cost calculated output (balance * buffer_rate * fraction).';
