-- Migration: Add financial_element to GL tables
ALTER TABLE stg_gl_data ADD COLUMN IF NOT EXISTS financial_element VARCHAR(20);
ALTER TABLE proc_gl_data ADD COLUMN IF NOT EXISTS financial_element VARCHAR(20);

COMMENT ON COLUMN stg_gl_data.financial_element IS 'Financial element code (e.g. BAL, II, COF) for this GL balance.';
COMMENT ON COLUMN proc_gl_data.financial_element IS 'Financial element code (e.g. BAL, II, COF) for this GL balance.';
