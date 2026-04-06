-- sp_month_end_alloc
-- Template for a month-end allocation processing procedure.
-- Rename, copy, and adapt this file for each real month-end task.
--
-- Parameter naming convention (matches BankPFT batch token substitution):
--   p_as_of_date  →  resolved from {as_of_date} token  (ISO string, e.g. '2026-04-30')
--   p_run_by      →  resolved from {run_by} token       (username, e.g. 'admin')
--
-- To wire into a BatchDefinition:
--   1. Add a CUSTOM_SP task with ref_id = 'sp_month_end_alloc'
--   2. Set params_json = {"p_as_of_date": "{as_of_date}", "p_run_by": "{run_by}"}
--   3. The batch engine resolves tokens and dispatches the procedure asynchronously.
--
-- Deployment:
--   psql -U bankpft -d bankpft -f db/procedures/sp_month_end_alloc.sql

CREATE OR REPLACE PROCEDURE sp_month_end_alloc(
    p_as_of_date  TEXT  DEFAULT NULL,
    p_run_by      TEXT  DEFAULT NULL
)
LANGUAGE plpgsql AS $$
DECLARE
    v_as_of  DATE;
    v_rows   INT := 0;
BEGIN
    -- ── 1. Input validation ────────────────────────────────────────────────────
    IF p_as_of_date IS NULL THEN
        RAISE EXCEPTION 'p_as_of_date is required';
    END IF;

    v_as_of := p_as_of_date::DATE;

    -- ── 2. Core processing — replace with real business logic ─────────────────
    --
    -- Example: materialise a month-end snapshot into a summary table:
    --
    --   INSERT INTO alloc_result_snapshot (as_of_date, account_id, alloc_amount, created_by)
    --   SELECT v_as_of, account_id, alloc_amount, p_run_by
    --   FROM   alloc_result
    --   WHERE  as_of_date = v_as_of
    --   ON CONFLICT (as_of_date, account_id)
    --   DO UPDATE SET alloc_amount = EXCLUDED.alloc_amount,
    --                 created_by   = EXCLUDED.created_by;
    --
    --   GET DIAGNOSTICS v_rows = ROW_COUNT;

    -- ── 3. Placeholder: nothing to do in the template ─────────────────────────
    GET DIAGNOSTICS v_rows = ROW_COUNT;

    -- ── 4. Completion notice (visible in PostgreSQL server logs) ──────────────
    RAISE NOTICE 'sp_month_end_alloc completed for %: % rows affected (run_by=%)',
        v_as_of, v_rows, p_run_by;
END;
$$;
