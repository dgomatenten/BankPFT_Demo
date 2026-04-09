-- ============================================================
-- sp_alloc_log_table.sql
-- Audit table for sp_run_allocation SQL execution events.
--
-- One row per logged event inside sp_run_allocation:
--   phase       — matches the SP phase number (1-9)
--   event_type  — PHASE_START | SQL_EXEC | NOTICE | SUMMARY | ERROR
--   event_label — short label e.g. 'DEBIT_INSERT', 'SOURCE_COUNT'
--   sql_text    — the fully-rendered SQL string passed to EXECUTE
--   row_count   — GET DIAGNOSTICS ROW_COUNT after the EXECUTE
--   message     — free-text notes (e.g. RAISE NOTICE body)
--
-- Deployment:
--   psql -U bankpft -d bankpft -f db/ddl/sp_alloc_log_table.sql
-- ============================================================

CREATE TABLE IF NOT EXISTS sp_alloc_log (
    id           BIGSERIAL    PRIMARY KEY,
    batch_id     TEXT         NOT NULL,
    phase        SMALLINT     NOT NULL DEFAULT 0,
    event_type   VARCHAR(20)  NOT NULL,   -- PHASE_START | SQL_EXEC | NOTICE | SUMMARY | ERROR
    event_label  VARCHAR(100),
    sql_text     TEXT,
    row_count    INTEGER,
    message      TEXT,
    logged_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sp_alloc_log_batch
    ON sp_alloc_log (batch_id);

COMMENT ON TABLE sp_alloc_log IS
    'Per-event SQL execution audit log for sp_run_allocation. '
    'Stores the rendered dynamic SQL before each EXECUTE call, '
    'along with the resulting row count and phase metadata.';
