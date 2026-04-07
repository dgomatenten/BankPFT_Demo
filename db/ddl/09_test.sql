-- ============================================================
-- 09_test.sql  —  In-App Test Suite Run Table
-- Tables: test_suite_run
-- ============================================================

CREATE TABLE IF NOT EXISTS test_suite_run (
    id           VARCHAR(36)   PRIMARY KEY,  -- UUID
    started_at   TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    triggered_by VARCHAR(50),
    -- Overall result
    status       VARCHAR(10)   NOT NULL DEFAULT 'RUNNING',  -- RUNNING | PASS | FAIL | ERROR
    total        INTEGER       NOT NULL DEFAULT 0,
    passed       INTEGER       NOT NULL DEFAULT 0,
    failed       INTEGER       NOT NULL DEFAULT 0,
    error        INTEGER       NOT NULL DEFAULT 0,
    skipped      INTEGER       NOT NULL DEFAULT 0,
    duration_s   NUMERIC(10,3) NOT NULL DEFAULT 0,
    -- Full pytest-json-report payload and captured stdout
    results_json JSONB,
    stdout       TEXT
);

COMMENT ON TABLE  test_suite_run             IS 'Records each in-app pytest invocation triggered from the /tests/ UI or API.';
COMMENT ON COLUMN test_suite_run.status      IS 'RUNNING while executing. PASS if all tests passed. FAIL if any test failed. ERROR on pytest crash.';
COMMENT ON COLUMN test_suite_run.results_json IS 'Full pytest-json-report output — individual test results, durations, and error traces.';
