-- ============================================================
-- 08_datafile.sql  —  Data File Import / Export Audit Table
-- Tables: datafile_batch
-- ============================================================

CREATE TABLE IF NOT EXISTS datafile_batch (
    id            VARCHAR(36)  PRIMARY KEY,  -- UUID
    operation     VARCHAR(10)  NOT NULL,      -- IMPORT | EXPORT
    format_id     VARCHAR(50)  NOT NULL,      -- key from datafile_config.json
    format_name   VARCHAR(100),
    filename      VARCHAR(255) NOT NULL,
    target_table  VARCHAR(50),               -- destination table name (imports only)
    status        VARCHAR(20)  NOT NULL DEFAULT 'RUNNING',  -- RUNNING | COMPLETED | FAILED
    row_count     INTEGER      NOT NULL DEFAULT 0,
    error_count   INTEGER      NOT NULL DEFAULT 0,
    errors_json   JSONB,                     -- JSON list of per-row error strings
    run_by        VARCHAR(50)  NOT NULL,
    started_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    completed_at  TIMESTAMPTZ,
    error_message TEXT
);

COMMENT ON TABLE  datafile_batch              IS 'Audit record for each data file import or export operation.';
COMMENT ON COLUMN datafile_batch.operation    IS 'IMPORT = fixed-length/delimited file loaded into a target table. EXPORT = data written to output file.';
COMMENT ON COLUMN datafile_batch.format_id    IS 'Matches the format key in datafile_config.json (e.g. import_loan, export_inst_proc).';
COMMENT ON COLUMN datafile_batch.target_table IS 'Destination database table for IMPORT operations (NULL for EXPORT).';

CREATE INDEX IF NOT EXISTS ix_datafile_batch_format_id  ON datafile_batch(format_id);
CREATE INDEX IF NOT EXISTS ix_datafile_batch_started_at ON datafile_batch(started_at);
