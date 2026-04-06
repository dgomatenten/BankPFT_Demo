-- sp_test_echo
-- Minimal stored procedure used exclusively by integration tests.
-- Writes one row to sp_call_log so the test can verify the procedure ran.
--
-- Parameters intentionally use TEXT so that no implicit cast from the
-- SQLAlchemy bind-parameter string is required; batch_executor always
-- resolves as_of_date to an ISO string before dispatch.
--
-- Usage:
--   CALL sp_test_echo('2026-04-06', 'system');

CREATE OR REPLACE PROCEDURE sp_test_echo(
    p_as_of_date  TEXT  DEFAULT NULL,
    p_run_by      TEXT  DEFAULT NULL
)
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO sp_call_log (sp_name, called_by, as_of_date)
    VALUES (
        'sp_test_echo',
        p_run_by,
        CASE WHEN p_as_of_date IS NOT NULL
             THEN p_as_of_date::DATE
             ELSE NULL
        END
    );
END;
$$;
