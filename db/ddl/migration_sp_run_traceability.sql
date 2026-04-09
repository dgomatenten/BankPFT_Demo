-- ============================================================
-- migration_sp_run_traceability.sql
-- Adds SQL execution traceability columns to sp_run,
-- and creates sp_alloc_log if not already deployed separately.
--
-- Run once against the bankpft database after deploying
-- sp_run_allocation.sql and sp_alloc_log_table.sql.
--
-- Idempotent: uses ADD COLUMN IF NOT EXISTS.
--
-- Deployment:
--   psql -U bankpft -d bankpft -f db/ddl/migration_sp_run_traceability.sql
-- ============================================================

-- 1. Add traceability columns to sp_run
ALTER TABLE sp_run
    ADD COLUMN IF NOT EXISTS executed_sql  TEXT,
    ADD COLUMN IF NOT EXISTS notices_log   TEXT;

COMMENT ON COLUMN sp_run.executed_sql IS
    'The rendered CALL statement sent to the database, '
    'e.g. CALL sp_run_allocation(:p_rule_id, :p_as_of_date, :p_run_by)';

COMMENT ON COLUMN sp_run.notices_log IS
    'Human-readable summary built from sp_alloc_log rows after execution. '
    'Only populated for sp_run_allocation calls.';

-- 2. Create sp_alloc_log if not deployed separately
CREATE TABLE IF NOT EXISTS sp_alloc_log (
    id           BIGSERIAL    PRIMARY KEY,
    batch_id     TEXT         NOT NULL,
    phase        SMALLINT     NOT NULL DEFAULT 0,
    event_type   VARCHAR(20)  NOT NULL,
    event_label  VARCHAR(100),
    sql_text     TEXT,
    row_count    INTEGER,
    message      TEXT,
    logged_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sp_alloc_log_batch
    ON sp_alloc_log (batch_id);

-- Done
SELECT 'Migration complete: sp_run + sp_alloc_log traceability columns applied.' AS result;
