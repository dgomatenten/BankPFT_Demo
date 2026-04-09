-- migration_sp_registry.sql
-- Create table for sys_registered_sp to enable stored procedure registration for the Batch framework.

CREATE TABLE IF NOT EXISTS sys_registered_sp (
    id SERIAL PRIMARY KEY,
    procedure_name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    is_batch_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE sys_registered_sp IS 'Registers user-defined stored procedures for execution within the batch framework.';
COMMENT ON COLUMN sys_registered_sp.procedure_name IS 'The schema-qualified name of the SP (e.g. reporting.sp_extract_data).';
COMMENT ON COLUMN sys_registered_sp.is_batch_enabled IS 'Controls if this SP surfaces in the Batch Configurator dropdown UI.';
