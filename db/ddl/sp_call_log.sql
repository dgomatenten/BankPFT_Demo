-- sp_call_log
-- Lightweight audit table written to by test stored procedures.
-- Used by integration tests (tests/test_sp_integration.py) to verify that
-- sp_test_echo actually executed inside PostgreSQL.
--
-- This table is NOT part of the main application schema; it is created and
-- dropped by the integration test session fixture (pg_db_objects).

CREATE TABLE IF NOT EXISTS sp_call_log (
    id          SERIAL       PRIMARY KEY,
    sp_name     TEXT         NOT NULL,
    called_by   TEXT,
    as_of_date  DATE,
    called_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);
