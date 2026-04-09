-- ============================================================
-- 12_json_config.sql  —  JSON Configuration Store
-- Stores application JSON configs in the database so both
-- the Python app and PostgreSQL stored procedures share a
-- single source of truth.
-- ============================================================

CREATE TABLE IF NOT EXISTS json_config (
    id           SERIAL        PRIMARY KEY,
    config_name  VARCHAR(100)  NOT NULL UNIQUE,
    description  TEXT,
    config_data  JSONB         NOT NULL,
    is_active    BOOLEAN       NOT NULL DEFAULT TRUE,
    updated_at   TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_by   VARCHAR(50)
);

COMMENT ON TABLE  json_config              IS 'Application JSON configuration store — shared between Python and stored procedures.';
COMMENT ON COLUMN json_config.config_name  IS 'Unique identifier matching the filesystem config file stem (e.g. allocation_engine_config).';
COMMENT ON COLUMN json_config.config_data  IS 'Full JSON content stored as JSONB for native querying.';

CREATE INDEX IF NOT EXISTS ix_json_config_name ON json_config(config_name);


-- ──────────────────────────────────────────────────────────
-- Helper function: retrieve a named config as JSONB
-- Used by stored procedures to read engine configuration.
--
-- Usage:
--   SELECT fn_get_config('allocation_engine_config');
--   SELECT fn_get_config('allocation_engine_config') -> 'source_tables' -> 'proc_inst_data';
-- ──────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION fn_get_config(p_name TEXT)
RETURNS JSONB
LANGUAGE sql STABLE AS $$
    SELECT config_data
      FROM json_config
     WHERE config_name = p_name
       AND is_active = TRUE
     LIMIT 1;
$$;
