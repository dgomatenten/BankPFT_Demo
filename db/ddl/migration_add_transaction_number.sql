-- Add transaction_number to stg_inst_data
ALTER TABLE stg_inst_data ADD COLUMN IF NOT EXISTS transaction_number VARCHAR(100);

-- Add transaction_number to proc_inst_data
ALTER TABLE proc_inst_data ADD COLUMN IF NOT EXISTS transaction_number VARCHAR(100);

-- Add transaction_number to fct_mgmt_instrument
ALTER TABLE fct_mgmt_instrument ADD COLUMN IF NOT EXISTS transaction_number VARCHAR(100);
