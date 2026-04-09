-- ============================================================
-- sp_run_allocation.sql
-- PostgreSQL stored procedure version of the BankPFT allocation engine.
--
-- Mirrors the Python engine (app/services/allocation_engine.py)
-- with set-based SQL for high-performance batch processing.
--
-- Supports:
--   • RATIO, DISTRIBUTION, STATIC allocation methods
--   • Source tables: proc_inst_data, proc_gl_data, fct_mgmt_ledger, fct_mgmt_instrument
--   • Lookup tables: ref_static_allocation, ref_org_reclass,
--                     ref_static_distribution, ref_static_alloc
--   • Output tables: fct_mgmt_ledger, fct_mgmt_instrument
--   • Financial element unpivot (BAL, II, COF) for proc_inst_data
--   • Output/Credit dimension mapping (same_as_source, lookup, fixed)
--   • Source dimension member filtering (source_dim_json)
--   • General row filtering (filter_json with AND/OR logic)
--   • Zero-balance row exclusion
--   • Orphan handling (unmatched source rows)
--   • Idempotent delete + insert
--   • Entry mode (BOTH, DEBIT_ONLY, CREDIT_ONLY)
--   • Batch run audit record (batch_run table)
--
-- Usage:
--   CALL sp_run_allocation(1, '2026-03-31', 'admin');
--
-- Wire into a BatchDefinition:
--   Task type: CUSTOM_SP, ref_id = 'sp_run_allocation'
--   params_json: {"p_rule_id":"42","p_as_of_date":"{as_of_date}","p_run_by":"{run_by}"}
--
-- Deployment:
--   psql -U bankpft -d bankpft -f db/procedures/sp_run_allocation.sql
-- ============================================================

-- Prerequisite: ensure financial_element column exists on output tables
ALTER TABLE fct_mgmt_ledger     ADD COLUMN IF NOT EXISTS financial_element VARCHAR(20);
ALTER TABLE fct_mgmt_instrument ADD COLUMN IF NOT EXISTS financial_element VARCHAR(20);


-- ──────────────────────────────────────────────────────────────────────────────
-- Helper: build a SQL expression that resolves a dimension value
--         based on the JSONB dimension config (output_dim_json / credit_dim_json).
--
-- Modes:
--   same_as_source — return p_fallback_expr (source column reference)
--   fixed          — return a literal value from the config
--   lookup         — return a lookup-table column reference (l.{column})
-- ──────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION fn_alloc_dim_expr(
    p_dim_cfg       JSONB,          -- full output_dim_json or credit_dim_json
    p_dim_key       TEXT,           -- dimension key, e.g. 'customer_id'
    p_fallback_expr TEXT,           -- SQL expression for same_as_source, e.g. 's.customer_id'
    p_lkp_alias     TEXT DEFAULT NULL  -- lookup table alias ('l'), NULL for STATIC
) RETURNS TEXT
LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE
    v_cfg   JSONB;
    v_mode  TEXT;
BEGIN
    v_cfg := p_dim_cfg -> p_dim_key;
    IF v_cfg IS NULL THEN
        RETURN p_fallback_expr;
    END IF;

    v_mode := COALESCE(v_cfg ->> 'mode', 'same_as_source');

    IF v_mode = 'fixed' THEN
        RETURN format('%L', COALESCE(v_cfg ->> 'value', ''));
    ELSIF v_mode = 'lookup' AND p_lkp_alias IS NOT NULL THEN
        RETURN format('%s.%I', p_lkp_alias, COALESCE(v_cfg ->> 'lookup_column', 'target_org_unit_id'));
    ELSE
        RETURN p_fallback_expr;   -- same_as_source (default)
    END IF;
END;
$$;


-- ──────────────────────────────────────────────────────────────────────────────
-- Helper: build WHERE clause fragment from filter_json
--
-- Supported operators:
--   eq, neq, gt, gte, lt, lte, between, in, not_in, contains, starts_with
-- ──────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION fn_alloc_filter_where(
    p_filter  JSONB,
    p_alias   TEXT           -- table alias ('s')
) RETURNS TEXT
LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE
    v_conditions JSONB;
    v_logic      TEXT;
    v_cond       JSONB;
    v_parts      TEXT[] := '{}';
    v_col        TEXT;
    v_op         TEXT;
    v_val        TEXT;
    v_sql_part   TEXT;
    v_vals       TEXT[];
    i            INT;
    j            INT;
BEGIN
    IF p_filter IS NULL THEN RETURN ''; END IF;

    v_conditions := p_filter -> 'conditions';
    IF v_conditions IS NULL OR jsonb_array_length(v_conditions) = 0 THEN
        RETURN '';
    END IF;

    v_logic := COALESCE(UPPER(p_filter ->> 'logic'), 'AND');

    FOR i IN 0 .. jsonb_array_length(v_conditions) - 1 LOOP
        v_cond := v_conditions -> i;
        v_col  := v_cond ->> 'field';
        v_op   := v_cond ->> 'operator';
        v_val  := COALESCE(v_cond ->> 'value', '');

        IF v_col IS NULL OR v_op IS NULL THEN CONTINUE; END IF;

        CASE v_op
            WHEN 'eq' THEN
                v_sql_part := format('%s.%I::TEXT = %L', p_alias, v_col, v_val);
            WHEN 'neq' THEN
                v_sql_part := format('%s.%I::TEXT <> %L', p_alias, v_col, v_val);
            WHEN 'gt' THEN
                v_sql_part := format('%s.%I::NUMERIC > %L::NUMERIC', p_alias, v_col, v_val);
            WHEN 'gte' THEN
                v_sql_part := format('%s.%I::NUMERIC >= %L::NUMERIC', p_alias, v_col, v_val);
            WHEN 'lt' THEN
                v_sql_part := format('%s.%I::NUMERIC < %L::NUMERIC', p_alias, v_col, v_val);
            WHEN 'lte' THEN
                v_sql_part := format('%s.%I::NUMERIC <= %L::NUMERIC', p_alias, v_col, v_val);
            WHEN 'between' THEN
                v_vals := string_to_array(v_val, ',');
                IF array_length(v_vals, 1) = 2 THEN
                    v_sql_part := format('%s.%I::NUMERIC BETWEEN %L::NUMERIC AND %L::NUMERIC',
                        p_alias, v_col, trim(v_vals[1]), trim(v_vals[2]));
                ELSE
                    CONTINUE;
                END IF;
            WHEN 'in' THEN
                v_vals := string_to_array(v_val, ',');
                v_sql_part := format('%s.%I::TEXT IN (', p_alias, v_col);
                FOR j IN 1 .. array_length(v_vals, 1) LOOP
                    IF j > 1 THEN v_sql_part := v_sql_part || ', '; END IF;
                    v_sql_part := v_sql_part || format('%L', trim(v_vals[j]));
                END LOOP;
                v_sql_part := v_sql_part || ')';
            WHEN 'not_in' THEN
                v_vals := string_to_array(v_val, ',');
                v_sql_part := format('%s.%I::TEXT NOT IN (', p_alias, v_col);
                FOR j IN 1 .. array_length(v_vals, 1) LOOP
                    IF j > 1 THEN v_sql_part := v_sql_part || ', '; END IF;
                    v_sql_part := v_sql_part || format('%L', trim(v_vals[j]));
                END LOOP;
                v_sql_part := v_sql_part || ')';
            WHEN 'contains' THEN
                v_sql_part := format('%s.%I::TEXT ILIKE %L', p_alias, v_col, '%' || v_val || '%');
            WHEN 'starts_with' THEN
                v_sql_part := format('%s.%I::TEXT LIKE %L', p_alias, v_col, v_val || '%');
            ELSE
                CONTINUE;
        END CASE;

        v_parts := array_append(v_parts, v_sql_part);
    END LOOP;

    IF array_length(v_parts, 1) IS NULL OR array_length(v_parts, 1) = 0 THEN
        RETURN '';
    END IF;

    RETURN ' AND (' || array_to_string(v_parts, ' ' || v_logic || ' ') || ')';
END;
$$;


-- ──────────────────────────────────────────────────────────────────────────────
-- Helper: build WHERE clause fragment from source_dim_json
--
-- For each dimension key with mode='specific', generates:
--   AND s.{dim_col}::TEXT IN ('member1', 'member2', ...)
-- ──────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION fn_alloc_sdim_where(
    p_source_dim JSONB,
    p_alias      TEXT
) RETURNS TEXT
LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE
    v_key     TEXT;
    v_cfg     JSONB;
    v_members JSONB;
    v_parts   TEXT[] := '{}';
    v_vals    TEXT[] := '{}';
    i         INT;
BEGIN
    IF p_source_dim IS NULL OR p_source_dim = '{}'::JSONB THEN
        RETURN '';
    END IF;

    FOR v_key IN SELECT jsonb_object_keys(p_source_dim) LOOP
        v_cfg := p_source_dim -> v_key;
        IF COALESCE(v_cfg ->> 'mode', 'all') <> 'specific' THEN CONTINUE; END IF;

        v_members := v_cfg -> 'members';
        IF v_members IS NULL OR jsonb_array_length(v_members) = 0 THEN CONTINUE; END IF;

        v_vals := '{}';
        FOR i IN 0 .. jsonb_array_length(v_members) - 1 LOOP
            IF trim(v_members ->> i) <> '' THEN
                v_vals := array_append(v_vals, format('%L', trim(v_members ->> i)));
            END IF;
        END LOOP;

        IF array_length(v_vals, 1) > 0 THEN
            v_parts := array_append(v_parts,
                format('%s.%I::TEXT IN (%s)', p_alias, v_key, array_to_string(v_vals, ', ')));
        END IF;
    END LOOP;

    IF array_length(v_parts, 1) IS NULL OR array_length(v_parts, 1) = 0 THEN
        RETURN '';
    END IF;

    RETURN ' AND ' || array_to_string(v_parts, ' AND ');
END;
$$;


-- ══════════════════════════════════════════════════════════════════════════════
-- MAIN PROCEDURE: sp_run_allocation
-- ══════════════════════════════════════════════════════════════════════════════
CREATE OR REPLACE PROCEDURE sp_run_allocation(
    p_rule_id     INTEGER,
    p_as_of_date  TEXT,
    p_run_by      TEXT  DEFAULT 'system'
)
LANGUAGE plpgsql AS $$
-- ─────────────────────────────────────────────────────────────────────────────
-- Logging: every dynamic SQL statement is written to sp_alloc_log before
-- EXECUTE. Pattern:
--   v_log_id := fn_sp_log(v_batch_id, phase, 'SQL_EXEC', label, sql, NULL, msg);
--   EXECUTE v_sql;  GET DIAGNOSTICS v_count = ROW_COUNT;
--   UPDATE sp_alloc_log SET row_count = v_count WHERE id = v_log_id;
-- ─────────────────────────────────────────────────────────────────────────────
DECLARE
    v_as_of           DATE;
    v_batch_id        TEXT;

    -- Rule fields
    v_alloc_method    TEXT;
    v_source_table    TEXT;
    v_lookup_table    TEXT;
    v_output_table    TEXT;
    v_join_key        TEXT;
    v_entry_mode      TEXT;
    v_balance_column  TEXT;
    v_dist_driver     TEXT;
    v_gen_offset      BOOLEAN;
    v_agg_source      BOOLEAN;

    -- JSONB dimension configs
    v_source_dim      JSONB;
    v_output_dim      JSONB;
    v_credit_dim      JSONB;
    v_filter          JSONB;

    -- Source table column mappings
    v_acct_col        TEXT;       -- account id column name
    v_ou_col          TEXT;       -- org unit column name
    v_date_col        TEXT := 'as_of_date';
    v_has_fe          BOOLEAN;    -- financial element unpivot?
    v_has_cust        BOOLEAN;    -- source has customer_id?
    v_has_prod        BOOLEAN;    -- source has product_code?

    -- Lookup table column mappings
    v_lkp_id_col      TEXT;
    v_lkp_ratio_col   TEXT := 'ratio';
    v_lkp_tgt_org_col TEXT;
    v_lkp_date_col    TEXT := 'as_of_date';
    v_lkp_status      TEXT := 'APPROVED';

    -- SQL building blocks
    v_sql              TEXT;
    v_insert_cols      TEXT;
    v_from_clause      TEXT;
    v_join_clause      TEXT := '';
    v_where_base       TEXT;
    v_where_filter     TEXT := '';
    v_where_sdim       TEXT := '';
    v_where_zero       TEXT := '';
    v_fe_join          TEXT := '';
    v_lkp_alias        TEXT := NULL;

    -- Engine config from json_config table
    v_engine_cfg       JSONB;
    v_src_cfg          JSONB;       -- source_tables -> {source_table}
    v_lkp_cfg          JSONB;       -- lookup_tables -> {lookup_table}
    v_fe_cols          JSONB;       -- financial_element_columns
    v_bal_cols          JSONB;       -- balance_columns array

    -- Source column expressions
    v_acct_expr        TEXT;
    v_cust_expr        TEXT;
    v_prod_expr        TEXT;
    v_org_expr         TEXT;

    -- Financial element / balance expressions
    v_fe_label_expr    TEXT;
    v_src_bal_expr     TEXT;
    v_alloc_bal_expr   TEXT;
    v_alloc_inc_expr   TEXT;
    v_ratio_expr       TEXT;

    -- Dimension output expressions (DEBIT)
    v_d_acct           TEXT;
    v_d_cust           TEXT;
    v_d_prod           TEXT;
    v_d_org_tgt        TEXT;

    -- Dimension output expressions (CREDIT)
    v_c_acct           TEXT;
    v_c_cust           TEXT;
    v_c_prod           TEXT;
    v_c_org_tgt        TEXT;

    -- Counters
    v_del_count        INT := 0;
    v_src_count        INT := 0;
    v_debit_count      INT := 0;
    v_credit_count     INT := 0;
    v_orphan_count     INT := 0;
    v_src_total        NUMERIC := 0;
    v_out_total        NUMERIC := 0;

    -- Org config key (for dim resolution)
    v_org_cfg_key      TEXT;

    -- Join condition parts
    v_join_cols        TEXT[];
    v_join_cond        TEXT;
    k                  INT;

    -- Audit logging: track the last sp_alloc_log row id so we can back-fill row_count
    v_log_id           BIGINT;
BEGIN
    -- ═══════════════════════════════════════════════════════════════════════
    -- PHASE 1: Input validation
    -- ═══════════════════════════════════════════════════════════════════════
    IF p_rule_id IS NULL THEN
        RAISE EXCEPTION 'p_rule_id is required';
    END IF;
    IF p_as_of_date IS NULL THEN
        RAISE EXCEPTION 'p_as_of_date is required';
    END IF;
    v_as_of    := p_as_of_date::DATE;
    v_batch_id := gen_random_uuid()::TEXT;

    INSERT INTO sp_alloc_log (batch_id, phase, event_type, event_label, message)
    VALUES (v_batch_id, 1, 'PHASE_START', 'INPUT_VALIDATION',
            format('p_rule_id=%s, p_as_of_date=%s, p_run_by=%s',
                   p_rule_id, p_as_of_date, p_run_by));

    -- ═══════════════════════════════════════════════════════════════════════
    -- PHASE 2: Load rule configuration
    -- ═══════════════════════════════════════════════════════════════════════
    INSERT INTO sp_alloc_log (batch_id, phase, event_type, event_label, message)
    VALUES (v_batch_id, 2, 'PHASE_START', 'LOAD_RULE',
            format('Loading allocation_rule id=%s', p_rule_id));

    SELECT
        UPPER(COALESCE(allocation_method, 'RATIO')),
        source_table,
        lookup_table,
        COALESCE(output_table, 'fct_mgmt_ledger'),
        join_key,
        UPPER(COALESCE(entry_mode, '')),
        balance_column,
        distribution_driver,
        COALESCE(generate_offset, TRUE),
        COALESCE(aggregate_source, FALSE),
        COALESCE(source_dim_json, '{}'::JSONB),
        COALESCE(output_dim_json, '{}'::JSONB),
        COALESCE(credit_dim_json, '{}'::JSONB),
        filter_json
    INTO
        v_alloc_method, v_source_table, v_lookup_table, v_output_table,
        v_join_key, v_entry_mode, v_balance_column, v_dist_driver,
        v_gen_offset, v_agg_source, v_source_dim, v_output_dim, v_credit_dim, v_filter
    FROM allocation_rule
    WHERE id = p_rule_id AND is_active = TRUE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Rule % not found or is inactive', p_rule_id;
    END IF;

    -- Normalize entry_mode
    IF v_entry_mode NOT IN ('BOTH', 'DEBIT_ONLY', 'CREDIT_ONLY') THEN
        v_entry_mode := CASE WHEN v_gen_offset THEN 'BOTH' ELSE 'DEBIT_ONLY' END;
    END IF;

    -- Normalize allocation method
    IF v_alloc_method NOT IN ('RATIO', 'DISTRIBUTION', 'STATIC') THEN
        v_alloc_method := 'RATIO';
    END IF;

    INSERT INTO sp_alloc_log (batch_id, phase, event_type, event_label, message)
    VALUES (v_batch_id, 2, 'NOTICE', 'RULE_CONFIG',
            format('method=%s | source=%s | lookup=%s | output=%s | entry_mode=%s | as_of_date=%s',
                   v_alloc_method, v_source_table, v_lookup_table,
                   v_output_table, v_entry_mode, v_as_of));

    -- ═══════════════════════════════════════════════════════════════════════
    -- PHASE 3: Load engine config from json_config table, resolve column mappings
    -- ═══════════════════════════════════════════════════════════════════════
    INSERT INTO sp_alloc_log (batch_id, phase, event_type, event_label, message)
    VALUES (v_batch_id, 3, 'PHASE_START', 'LOAD_ENGINE_CONFIG',
            'Reading allocation_engine_config from json_config');

    v_engine_cfg := fn_get_config('allocation_engine_config');
    IF v_engine_cfg IS NULL THEN
        RAISE EXCEPTION 'allocation_engine_config not found in json_config table. '
                        'Sync configs via Admin → JSON Configurations → Sync All.';
    END IF;

    -- Source table config
    v_src_cfg := v_engine_cfg -> 'source_tables' -> v_source_table;
    IF v_src_cfg IS NULL THEN
        RAISE EXCEPTION 'No config for source table "%" in allocation_engine_config', v_source_table;
    END IF;

    v_acct_col := v_src_cfg ->> 'account_id_column';
    v_ou_col   := COALESCE(v_src_cfg ->> 'org_unit_column', 'org_unit_id');
    v_date_col := COALESCE(v_src_cfg ->> 'date_filter_column', 'as_of_date');
    v_fe_cols  := v_src_cfg -> 'financial_element_columns';     -- NULL or {"balance":"BAL",...}
    v_has_fe   := (v_fe_cols IS NOT NULL AND v_fe_cols <> '{}'::JSONB);
    v_bal_cols := v_src_cfg -> 'balance_columns';               -- ["balance","interest_income",...]

    -- Detect source column capabilities from config columns array
    v_has_cust := (v_src_cfg -> 'columns') ? 'customer_id';
    v_has_prod := (v_src_cfg -> 'columns') ? 'product_code';

    -- Output table validation
    IF v_engine_cfg -> 'output_tables' -> v_output_table IS NULL THEN
        RAISE EXCEPTION 'No config for output table "%" in allocation_engine_config', v_output_table;
    END IF;

    -- Lookup table config (only for RATIO/DISTRIBUTION)
    IF v_alloc_method IN ('RATIO', 'DISTRIBUTION') THEN
        v_lkp_cfg := v_engine_cfg -> 'lookup_tables' -> v_lookup_table;
        IF v_lkp_cfg IS NULL THEN
            RAISE EXCEPTION 'No config for lookup table "%" in allocation_engine_config', v_lookup_table;
        END IF;

        v_lkp_id_col      := v_lkp_cfg ->> 'id_column';
        v_lkp_ratio_col   := COALESCE(v_lkp_cfg ->> 'ratio_column', 'ratio');
        v_lkp_tgt_org_col := v_lkp_cfg ->> 'target_org_column';
        v_lkp_date_col    := COALESCE(v_lkp_cfg ->> 'date_filter_column', 'as_of_date');
        v_lkp_status      := COALESCE(v_lkp_cfg ->> 'status_filter', 'APPROVED');
        v_lkp_alias := 'l';
    END IF;

    RAISE NOTICE 'sp_run_allocation: rule=%, method=%, source=%, lookup=%, output=%, '
                 'entry_mode=%, as_of_date=%',
        p_rule_id, v_alloc_method, v_source_table, v_lookup_table,
        v_output_table, v_entry_mode, v_as_of;

    -- ═══════════════════════════════════════════════════════════════════════
    -- PHASE 4: Create batch_run record (status = RUNNING)
    -- ═══════════════════════════════════════════════════════════════════════
    INSERT INTO sp_alloc_log (batch_id, phase, event_type, event_label, message)
    VALUES (v_batch_id, 4, 'PHASE_START', 'CREATE_BATCH_RUN',
            format('batch_run id=%s, rule_id=%s, run_by=%s',
                   v_batch_id, p_rule_id, p_run_by));

    INSERT INTO batch_run (id, rule_id, as_of_date, status, run_by, started_at)
    VALUES (v_batch_id, p_rule_id, v_as_of, 'RUNNING', COALESCE(p_run_by, 'system'), NOW());

    BEGIN  -- Nested block for error handling → marks batch FAILED on exception

    -- ═══════════════════════════════════════════════════════════════════════
    -- PHASE 5: Count source rows & validate data exists
    -- ═══════════════════════════════════════════════════════════════════════
    v_sql := format('SELECT COUNT(*) FROM %I WHERE %I = %L::DATE',
                    v_source_table, v_date_col, v_as_of);

    INSERT INTO sp_alloc_log (batch_id, phase, event_type, event_label, sql_text, message)
    VALUES (v_batch_id, 5, 'SQL_EXEC', 'SOURCE_COUNT', v_sql,
            format('Counting source rows in %s for as_of_date=%s', v_source_table, v_as_of))
    RETURNING id INTO v_log_id;

    EXECUTE format(
        'SELECT COUNT(*) FROM %I WHERE %I = $1',
        v_source_table, v_date_col
    ) INTO v_src_count USING v_as_of;

    UPDATE sp_alloc_log SET row_count = v_src_count WHERE id = v_log_id;

    IF v_src_count = 0 THEN
        INSERT INTO sp_alloc_log (batch_id, phase, event_type, event_label, message)
        VALUES (v_batch_id, 5, 'ERROR', 'NO_SOURCE_DATA',
                format('No rows in %s for %s — batch FAILED', v_source_table, v_as_of));
        UPDATE batch_run
           SET status = 'FAILED',
               error_message = format('No data in %s for %s', v_source_table, v_as_of),
               completed_at = NOW()
         WHERE id = v_batch_id;
        RAISE NOTICE 'sp_run_allocation: FAILED — no source data';
        RETURN;
    END IF;

    -- ═══════════════════════════════════════════════════════════════════════
    -- PHASE 6: Build SQL building blocks
    -- ═══════════════════════════════════════════════════════════════════════

    -- INSERT column list (same for all output tables)
    v_insert_cols := format(
        'INSERT INTO %I (batch_run_id, as_of_date, entry_type, financial_element, '
        'allocation_id, source_account_id, customer_id, product_code, '
        'source_org_unit_id, target_org_unit_id, '
        'source_balance, allocated_balance, allocated_income, ratio_applied, is_orphan)',
        v_output_table
    );

    -- FROM clause
    v_from_clause := format('FROM %I s', v_source_table);

    -- Base WHERE clause: as_of_date filter on source
    v_where_base := format('WHERE s.%I = %L::DATE', v_date_col, v_as_of);

    -- filter_json → extra WHERE conditions
    v_where_filter := fn_alloc_filter_where(v_filter, 's');

    -- source_dim_json → dimension member filters
    v_where_sdim := fn_alloc_sdim_where(v_source_dim, 's');

    -- Source column expressions
    v_acct_expr := format('s.%I', v_acct_col);
    v_cust_expr := CASE WHEN v_has_cust THEN 's.customer_id' ELSE '''''' END;
    v_prod_expr := CASE WHEN v_has_prod THEN 's.product_code' ELSE '''''' END;
    v_org_expr  := format('s.%I', v_ou_col);

    -- ─── Financial element / balance expressions ─────────────────────────
    IF v_has_fe THEN
        -- Unpivot: build CROSS JOIN LATERAL VALUES from financial_element_columns config
        -- e.g. {"balance":"BAL","interest_income":"II","cost_of_fund":"COF"}
        DECLARE
            v_fe_key    TEXT;
            v_fe_label  TEXT;
            v_fe_parts  TEXT[] := '{}';
            v_zero_parts TEXT[] := '{}';
        BEGIN
            IF v_balance_column IS NOT NULL AND v_fe_cols ? v_balance_column THEN
                -- Single balance column restriction
                v_fe_label := v_fe_cols ->> v_balance_column;
                v_fe_join := E'\nCROSS JOIN LATERAL (VALUES ('
                    || format('%L, COALESCE(s.%I, 0))', v_fe_label, v_balance_column)
                    || ') AS fe(label, val)';
                v_where_zero := format(' AND COALESCE(s.%I, 0) <> 0', v_balance_column);
            ELSE
                -- All financial element columns from config
                FOR v_fe_key IN SELECT jsonb_object_keys(v_fe_cols) LOOP
                    v_fe_label := v_fe_cols ->> v_fe_key;
                    v_fe_parts := array_append(v_fe_parts,
                        format('(%L, COALESCE(s.%I, 0))', v_fe_label, v_fe_key));
                    v_zero_parts := array_append(v_zero_parts,
                        format('COALESCE(s.%I, 0) <> 0', v_fe_key));
                END LOOP;

                v_fe_join := E'\nCROSS JOIN LATERAL (VALUES \n    '
                    || array_to_string(v_fe_parts, E',\n    ')
                    || E'\n) AS fe(label, val)';
                v_where_zero := ' AND (' || array_to_string(v_zero_parts, ' OR ') || ')';
            END IF;
        END;

        v_fe_label_expr  := 'fe.label';
        v_src_bal_expr   := 'fe.val';
        v_alloc_inc_expr := '0';   -- income is its own fe row

    ELSE
        -- Non-FE source tables: use balance_columns from config
        v_fe_label_expr := 'NULL';

        -- First balance column = source_balance
        IF v_bal_cols IS NOT NULL AND jsonb_array_length(v_bal_cols) > 0 THEN
            v_src_bal_expr := format('COALESCE(s.%I, 0)', v_bal_cols ->> 0);
            -- Second balance column = allocated_income (if exists)
            IF jsonb_array_length(v_bal_cols) > 1 THEN
                v_alloc_inc_expr := format('COALESCE(s.%I, 0)', v_bal_cols ->> 1);
                v_where_zero := format(' AND (COALESCE(s.%I, 0) <> 0 OR COALESCE(s.%I, 0) <> 0)',
                    v_bal_cols ->> 0, v_bal_cols ->> 1);
            ELSE
                v_alloc_inc_expr := '0';
                v_where_zero := format(' AND COALESCE(s.%I, 0) <> 0', v_bal_cols ->> 0);
            END IF;
        ELSE
            v_src_bal_expr   := 'COALESCE(s.balance, 0)';
            v_alloc_inc_expr := '0';
            v_where_zero     := ' AND COALESCE(s.balance, 0) <> 0';
        END IF;
    END IF;

    -- ═══════════════════════════════════════════════════════════════════════
    -- PHASE 5B: Materialise filtered source into session temp table _alloc_src
    --
    -- Captures the FULL source query (date + source_dim + filter_json)
    -- and logs it to sp_alloc_log as SOURCE_EXTRACT so it is auditable.
    -- All INSERT phases (DEBIT/CREDIT/ORPHAN) read from _alloc_src instead
    -- of the base source table, keeping per-INSERT SQL clean.
    -- ═══════════════════════════════════════════════════════════════════════
    IF v_agg_source THEN
        DECLARE
            v_dim_col TEXT;
            v_mode    TEXT;
            v_selects TEXT[] := '{}';
            v_groups  TEXT[] := '{}';
        BEGIN
            -- Dimensions
            FOR i IN 0 .. jsonb_array_length(v_src_cfg -> 'dimension_columns') - 1 LOOP
                v_dim_col := v_src_cfg -> 'dimension_columns' ->> i;
                v_mode := COALESCE(v_output_dim -> v_dim_col ->> 'mode', 'same_as_source');
                IF v_mode <> 'fixed' THEN
                    v_selects := array_append(v_selects, format('s.%I', v_dim_col));
                    v_groups  := array_append(v_groups, format('s.%I', v_dim_col));
                ELSE
                    -- Keep column in temp table layout but don't partition groups by it
                    v_selects := array_append(v_selects, format('MAX(s.%I) AS %I', v_dim_col, v_dim_col));
                END IF;
            END LOOP;
            
            -- Balances
            FOR i IN 0 .. jsonb_array_length(v_src_cfg -> 'balance_columns') - 1 LOOP
                v_dim_col := v_src_cfg -> 'balance_columns' ->> i;
                v_selects := array_append(v_selects, format('SUM(COALESCE(s.%I, 0)) AS %I', v_dim_col, v_dim_col));
            END LOOP;

            -- Ensure join_key is grouped (if missing from dimension array for some reason)
            IF array_position(v_groups, format('s.%I', v_join_key)) IS NULL AND v_join_key <> '' THEN
                v_selects := array_append(v_selects, format('s.%I', v_join_key));
                v_groups  := array_append(v_groups, format('s.%I', v_join_key));
            END IF;

            -- Explicit non-aggregated columns required for table layout
            v_selects := array_append(v_selects, format('MAX(s.%I) AS %I', v_date_col, v_date_col));

            v_sql := format('SELECT %s FROM %I s', array_to_string(v_selects, ', '), v_source_table)
                || format(E'\nWHERE s.%I = %L::DATE', v_date_col, v_as_of)
                || v_where_sdim
                || v_where_filter
                || v_where_zero
                || E'\nGROUP BY ' || array_to_string(v_groups, ', ');
        END;
    ELSE
        -- No aggregation, straight pass-through
        v_sql := format('SELECT * FROM %I s', v_source_table)
            || format(E'\nWHERE s.%I = %L::DATE', v_date_col, v_as_of)
            || v_where_sdim      -- AND s.{dim}::TEXT IN (...) for specific members
            || v_where_filter    -- AND (filter_json conditions)
            || v_where_zero;     -- AND balance <> 0 (always applies at source level)
    END IF;

    INSERT INTO sp_alloc_log (batch_id, phase, event_type, event_label, sql_text, message)
    VALUES (v_batch_id, 5, 'SQL_EXEC', 'SOURCE_EXTRACT', v_sql,
            format('Materialising filtered source from %s into _alloc_src (as_of=%s)',
                   v_source_table, v_as_of))
    RETURNING id INTO v_log_id;

    EXECUTE 'DROP TABLE IF EXISTS _alloc_src';
    EXECUTE 'CREATE TEMP TABLE _alloc_src ON COMMIT DROP AS ' || v_sql;
    GET DIAGNOSTICS v_src_count = ROW_COUNT;  -- refined count: filtered rows
    UPDATE sp_alloc_log SET row_count = v_src_count WHERE id = v_log_id;

    RAISE NOTICE 'sp_run_allocation: _alloc_src created with % rows (filtered)', v_src_count;

    IF v_src_count = 0 THEN
        INSERT INTO sp_alloc_log (batch_id, phase, event_type, event_label, message)
        VALUES (v_batch_id, 5, 'ERROR', 'NO_FILTERED_SOURCE',
                format('After applying source_dim and filter_json, %s has 0 rows for %s — batch FAILED',
                       v_source_table, v_as_of));
        UPDATE batch_run
           SET status = 'FAILED',
               error_message = format('No filtered source data in %s for %s (check source_dim_json / filter_json)',
                                      v_source_table, v_as_of),
               completed_at = NOW()
         WHERE id = v_batch_id;
        RAISE NOTICE 'sp_run_allocation: FAILED — no filtered source data';
        RETURN;
    END IF;

    -- Switch FROM clause to read from temp table for all INSERT phases
    v_from_clause := 'FROM _alloc_src s';
    -- Clear base predicates — they are baked into _alloc_src
    v_where_base   := '';
    v_where_sdim   := '';
    v_where_filter := '';

    -- ═══════════════════════════════════════════════════════════════════════
    -- PHASE 7: Delete existing output for this rule + as_of_date
    -- ═══════════════════════════════════════════════════════════════════════
    v_sql := format('DELETE FROM %I WHERE allocation_id = %L AND as_of_date = %L::DATE',
                    v_output_table, p_rule_id::TEXT, v_as_of);

    INSERT INTO sp_alloc_log (batch_id, phase, event_type, event_label, sql_text, message)
    VALUES (v_batch_id, 7, 'SQL_EXEC', 'DELETE_PRIOR',
            v_sql,
            format('Removing prior rows from %s for rule_id=%s, as_of_date=%s',
                   v_output_table, p_rule_id, v_as_of))
    RETURNING id INTO v_log_id;

    EXECUTE format(
        'DELETE FROM %I WHERE allocation_id = $1 AND as_of_date = $2',
        v_output_table
    ) USING p_rule_id::TEXT, v_as_of;
    GET DIAGNOSTICS v_del_count = ROW_COUNT;

    UPDATE sp_alloc_log SET row_count = v_del_count WHERE id = v_log_id;

    IF v_del_count > 0 THEN
        RAISE NOTICE 'sp_run_allocation: deleted % prior rows', v_del_count;
    END IF;

    -- ═══════════════════════════════════════════════════════════════════════
    -- PHASE 8: Execute allocation by method
    -- ═══════════════════════════════════════════════════════════════════════

    IF v_alloc_method IN ('RATIO', 'DISTRIBUTION') THEN
        -- ───────────────────────────────────────────────────────────────
        -- RATIO / DISTRIBUTION: source ↔ lookup JOIN
        -- ───────────────────────────────────────────────────────────────

        -- Build JOIN condition from join_key (may be comma-separated)
        v_join_cols := string_to_array(v_join_key, ',');
        v_join_cond := '';
        FOR k IN 1 .. array_length(v_join_cols, 1) LOOP
            IF k > 1 THEN v_join_cond := v_join_cond || ' AND '; END IF;
            v_join_cond := v_join_cond || format('s.%I = l.%I', trim(v_join_cols[k]), trim(v_join_cols[k]));
        END LOOP;

        -- Lookup WHERE conditions
        v_join_clause := format(
            E'\nINNER JOIN %I l ON %s'
            || E'\n    AND l.status = %L'
            || E'\n    AND (l.%I = %L::DATE OR l.%I IS NULL)',
            v_lookup_table, v_join_cond,
            v_lkp_status,
            v_lkp_date_col, v_as_of, v_lkp_date_col
        );

        -- Distribution driver filter
        IF v_alloc_method = 'DISTRIBUTION' AND v_dist_driver IS NOT NULL THEN
            v_join_clause := v_join_clause || format(E'\n    AND l.driver_name = %L', v_dist_driver);
        END IF;

        -- Ratio expression
        v_ratio_expr := format('l.%I', v_lkp_ratio_col);

        -- Resolve output dimension expressions for DEBIT
        -- Determine org config key: use 'target_org_unit_id' if it exists in config, else ou_col
        v_org_cfg_key := CASE
            WHEN v_output_dim ? 'target_org_unit_id' THEN 'target_org_unit_id'
            ELSE v_ou_col
        END;
        v_d_acct    := fn_alloc_dim_expr(v_output_dim, v_acct_col,    v_acct_expr, v_lkp_alias);
        v_d_cust    := fn_alloc_dim_expr(v_output_dim, 'customer_id', v_cust_expr, v_lkp_alias);
        v_d_prod    := fn_alloc_dim_expr(v_output_dim, 'product_code',v_prod_expr, v_lkp_alias);
        v_d_org_tgt := fn_alloc_dim_expr(v_output_dim, v_org_cfg_key,
                           format('l.%I', v_lkp_tgt_org_col), v_lkp_alias);

        -- Resolve credit dimension expressions
        v_org_cfg_key := CASE
            WHEN v_credit_dim ? 'target_org_unit_id' THEN 'target_org_unit_id'
            ELSE v_ou_col
        END;
        v_c_acct    := fn_alloc_dim_expr(v_credit_dim, v_acct_col,    v_acct_expr, v_lkp_alias);
        v_c_cust    := fn_alloc_dim_expr(v_credit_dim, 'customer_id', v_cust_expr, v_lkp_alias);
        v_c_prod    := fn_alloc_dim_expr(v_credit_dim, 'product_code',v_prod_expr, v_lkp_alias);
        v_c_org_tgt := fn_alloc_dim_expr(v_credit_dim, v_org_cfg_key, v_org_expr,  v_lkp_alias);

        -- ── DEBIT INSERT (matched rows) ──
        IF v_entry_mode IN ('BOTH', 'DEBIT_ONLY') THEN
            v_sql := v_insert_cols
                || E'\nSELECT '
                || format('%L, %L::DATE, ''DEBIT'', ', v_batch_id, v_as_of)
                || v_fe_label_expr || ', '
                || format('%L, ', p_rule_id::TEXT)
                || v_d_acct || ', '
                || v_d_cust || ', '
                || v_d_prod || ', '
                || v_org_expr || ', '       -- source_org_unit_id (always source)
                || v_d_org_tgt || ', '      -- target_org_unit_id
                || v_src_bal_expr || ', '
                || v_src_bal_expr || ' * ' || v_ratio_expr || ', '
                || v_alloc_inc_expr || CASE
                       WHEN v_alloc_inc_expr <> '0' THEN ' * ' || v_ratio_expr
                       ELSE ''
                   END || ', '
                || v_ratio_expr || ', FALSE'
                || E'\n' || v_from_clause
                || v_fe_join
                || v_join_clause
                || E'\n' || v_where_base
                || v_where_filter
                || v_where_sdim
                || v_where_zero;

            INSERT INTO sp_alloc_log (batch_id, phase, event_type, event_label, sql_text,
                                      message)
            VALUES (v_batch_id, 8, 'SQL_EXEC', 'DEBIT_INSERT', v_sql,
                    format('source=%s → output=%s | method=%s | entry_mode=%s',
                           v_source_table, v_output_table, v_alloc_method, v_entry_mode))
            RETURNING id INTO v_log_id;

            EXECUTE v_sql;
            GET DIAGNOSTICS v_debit_count = ROW_COUNT;

            UPDATE sp_alloc_log SET row_count = v_debit_count WHERE id = v_log_id;
        END IF;

        -- ── CREDIT INSERT (matched rows) ──
        IF v_entry_mode IN ('BOTH', 'CREDIT_ONLY') THEN
            v_sql := v_insert_cols
                || E'\nSELECT '
                || format('%L, %L::DATE, ''CREDIT'', ', v_batch_id, v_as_of)
                || v_fe_label_expr || ', '
                || format('%L, ', p_rule_id::TEXT)
                || v_c_acct || ', '
                || v_c_cust || ', '
                || v_c_prod || ', '
                || v_org_expr || ', '       -- source_org_unit_id (always source)
                || v_c_org_tgt || ', '      -- target_org_unit_id (credit defaults to source org)
                || v_src_bal_expr || ', '
                || '-(' || v_src_bal_expr || ' * ' || v_ratio_expr || '), '
                || CASE
                       WHEN v_alloc_inc_expr <> '0'
                       THEN '-(' || v_alloc_inc_expr || ' * ' || v_ratio_expr || ')'
                       ELSE '0'
                   END || ', '
                || v_ratio_expr || ', FALSE'
                || E'\n' || v_from_clause
                || v_fe_join
                || v_join_clause
                || E'\n' || v_where_base
                || v_where_filter
                || v_where_sdim
                || v_where_zero;

            INSERT INTO sp_alloc_log (batch_id, phase, event_type, event_label, sql_text,
                                      message)
            VALUES (v_batch_id, 8, 'SQL_EXEC', 'CREDIT_INSERT', v_sql,
                    format('source=%s → output=%s | method=%s | entry_mode=%s',
                           v_source_table, v_output_table, v_alloc_method, v_entry_mode))
            RETURNING id INTO v_log_id;

            EXECUTE v_sql;
            GET DIAGNOSTICS v_credit_count = ROW_COUNT;

            UPDATE sp_alloc_log SET row_count = v_credit_count WHERE id = v_log_id;
        END IF;

        -- ── ORPHAN INSERT (unmatched rows — DEBIT at ratio 1.0) ──
        -- Uses LEFT JOIN … WHERE l.id_col IS NULL + DISTINCT ON account
        v_sql := v_insert_cols
            || E'\nSELECT '
            || format('%L, %L::DATE, ''DEBIT'', ', v_batch_id, v_as_of)
            || v_fe_label_expr || ', '
            || format('%L, ', p_rule_id::TEXT)
            || v_acct_expr || ', '          -- account as-is
            || v_cust_expr || ', '
            || v_prod_expr || ', '
            || v_org_expr || ', '           -- source_org stays
            || v_org_expr || ', '           -- target_org = source_org for orphans
            || v_src_bal_expr || ', '
            || v_src_bal_expr || ', '       -- allocated_balance = source (ratio=1)
            || v_alloc_inc_expr || ', '     -- allocated_income as-is
            || '1.0, TRUE'
            || E'\n' || v_from_clause
            || v_fe_join
            || format(
                E'\nLEFT JOIN %I l ON %s AND l.status = %L AND (l.%I = %L::DATE OR l.%I IS NULL)',
                v_lookup_table, v_join_cond, v_lkp_status,
                v_lkp_date_col, v_as_of, v_lkp_date_col
            );

        -- Add distribution driver filter for LEFT JOIN too
        IF v_alloc_method = 'DISTRIBUTION' AND v_dist_driver IS NOT NULL THEN
            v_sql := v_sql || format(' AND l.driver_name = %L', v_dist_driver);
        END IF;

        -- _alloc_src already has date/dim/filter — only need lookup IS NULL + zero-balance
        v_sql := v_sql
            || format(E'\nWHERE l.%I IS NULL', v_lkp_id_col)    -- unmatched only
            || v_where_zero;

        INSERT INTO sp_alloc_log (batch_id, phase, event_type, event_label, sql_text, message)
        VALUES (v_batch_id, 8, 'SQL_EXEC', 'ORPHAN_INSERT', v_sql,
                'Inserting unmatched source rows as orphan DEBIT entries (ratio=1.0)')
        RETURNING id INTO v_log_id;

        EXECUTE v_sql;
        GET DIAGNOSTICS v_orphan_count = ROW_COUNT;

        UPDATE sp_alloc_log SET row_count = v_orphan_count WHERE id = v_log_id;

    ELSE
        -- ───────────────────────────────────────────────────────────────
        -- STATIC: direct 1:1 pass-through (ratio = 1.0, no lookup)
        -- ───────────────────────────────────────────────────────────────

        v_ratio_expr := '1.0';

        -- Resolve output dimension expressions for DEBIT
        v_d_acct    := fn_alloc_dim_expr(v_output_dim, v_acct_col,    v_acct_expr, NULL);
        v_d_cust    := fn_alloc_dim_expr(v_output_dim, 'customer_id', v_cust_expr, NULL);
        v_d_prod    := fn_alloc_dim_expr(v_output_dim, 'product_code',v_prod_expr, NULL);
        v_d_org_tgt := fn_alloc_dim_expr(v_output_dim, v_ou_col,      v_org_expr,  NULL);

        -- Resolve credit dimension expressions
        v_c_acct    := fn_alloc_dim_expr(v_credit_dim, v_acct_col,    v_acct_expr, NULL);
        v_c_cust    := fn_alloc_dim_expr(v_credit_dim, 'customer_id', v_cust_expr, NULL);
        v_c_prod    := fn_alloc_dim_expr(v_credit_dim, 'product_code',v_prod_expr, NULL);
        v_c_org_tgt := fn_alloc_dim_expr(v_credit_dim, v_ou_col,      v_org_expr,  NULL);

        -- ── DEBIT INSERT ──
        IF v_entry_mode IN ('BOTH', 'DEBIT_ONLY') THEN
            v_sql := v_insert_cols
                || E'\nSELECT '
                || format('%L, %L::DATE, ''DEBIT'', ', v_batch_id, v_as_of)
                || v_fe_label_expr || ', '
                || format('%L, ', p_rule_id::TEXT)
                || v_d_acct || ', '
                || v_d_cust || ', '
                || v_d_prod || ', '
                || v_org_expr || ', '
                || v_d_org_tgt || ', '
                || v_src_bal_expr || ', '
                || v_src_bal_expr || ', '    -- allocated = source (ratio=1)
                || v_alloc_inc_expr || ', '
                || v_ratio_expr || ', FALSE'
                || E'\n' || v_from_clause
                || v_fe_join;

            INSERT INTO sp_alloc_log (batch_id, phase, event_type, event_label, sql_text,
                                      message)
            VALUES (v_batch_id, 8, 'SQL_EXEC', 'DEBIT_INSERT', v_sql,
                    format('STATIC: source=%s → output=%s', v_source_table, v_output_table))
            RETURNING id INTO v_log_id;

            EXECUTE v_sql;
            GET DIAGNOSTICS v_debit_count = ROW_COUNT;

            UPDATE sp_alloc_log SET row_count = v_debit_count WHERE id = v_log_id;
        END IF;

        -- ── CREDIT INSERT ──
        IF v_entry_mode IN ('BOTH', 'CREDIT_ONLY') THEN
            v_sql := v_insert_cols
                || E'\nSELECT '
                || format('%L, %L::DATE, ''CREDIT'', ', v_batch_id, v_as_of)
                || v_fe_label_expr || ', '
                || format('%L, ', p_rule_id::TEXT)
                || v_c_acct || ', '
                || v_c_cust || ', '
                || v_c_prod || ', '
                || v_org_expr || ', '
                || v_c_org_tgt || ', '
                || v_src_bal_expr || ', '
                || '-(' || v_src_bal_expr || '), '    -- negated
                || CASE
                       WHEN v_alloc_inc_expr <> '0'
                       THEN '-(' || v_alloc_inc_expr || ')'
                       ELSE '0'
                   END || ', '
                || v_ratio_expr || ', FALSE'
                || E'\n' || v_from_clause
                || v_fe_join;

            INSERT INTO sp_alloc_log (batch_id, phase, event_type, event_label, sql_text,
                                      message)
            VALUES (v_batch_id, 8, 'SQL_EXEC', 'CREDIT_INSERT', v_sql,
                    format('STATIC: source=%s → output=%s', v_source_table, v_output_table))
            RETURNING id INTO v_log_id;

            EXECUTE v_sql;
            GET DIAGNOSTICS v_credit_count = ROW_COUNT;

            UPDATE sp_alloc_log SET row_count = v_credit_count WHERE id = v_log_id;
        END IF;

    END IF;  -- method branch

    -- ═══════════════════════════════════════════════════════════════════════
    -- PHASE 9: Calculate stats and update batch_run (COMPLETED)
    -- ═══════════════════════════════════════════════════════════════════════
    INSERT INTO sp_alloc_log (batch_id, phase, event_type, event_label, message)
    VALUES (v_batch_id, 9, 'PHASE_START', 'CALC_STATS',
            'Computing source_total and output_total');

    -- Get source total from the filtered temp table (_alloc_src) — matches what was allocated
    v_sql := format(
        'SELECT COALESCE(SUM(COALESCE(%I, 0)), 0) FROM _alloc_src',
        CASE v_source_table
            WHEN 'proc_inst_data' THEN COALESCE(v_balance_column, 'balance')
            WHEN 'proc_gl_data'   THEN 'balance'
            ELSE 'allocated_balance'
        END);

    INSERT INTO sp_alloc_log (batch_id, phase, event_type, event_label, sql_text, message)
    VALUES (v_batch_id, 9, 'SQL_EXEC', 'SOURCE_TOTAL', v_sql,
            format('Summing source balance from _alloc_src (%s filtered rows)', v_src_count))
    RETURNING id INTO v_log_id;

    EXECUTE format(
        'SELECT COALESCE(SUM(COALESCE(%I, 0)), 0) FROM _alloc_src',
        CASE v_source_table
            WHEN 'proc_inst_data' THEN COALESCE(v_balance_column, 'balance')
            WHEN 'proc_gl_data'   THEN 'balance'
            ELSE 'allocated_balance'
        END
    ) INTO v_src_total;

    UPDATE sp_alloc_log SET row_count = 1 WHERE id = v_log_id;  -- 1 = success

    -- Get output total (DEBIT allocated_balance only)
    v_sql := format(
        'SELECT COALESCE(SUM(allocated_balance), 0) FROM %I '
        'WHERE batch_run_id = %L AND entry_type = ''DEBIT''',
        v_output_table, v_batch_id);

    INSERT INTO sp_alloc_log (batch_id, phase, event_type, event_label, sql_text, message)
    VALUES (v_batch_id, 9, 'SQL_EXEC', 'OUTPUT_TOTAL', v_sql,
            format('Summing DEBIT allocated_balance from %s', v_output_table))
    RETURNING id INTO v_log_id;

    EXECUTE format(
        'SELECT COALESCE(SUM(allocated_balance), 0) FROM %I '
        'WHERE batch_run_id = $1 AND entry_type = ''DEBIT''',
        v_output_table
    ) INTO v_out_total USING v_batch_id;

    UPDATE sp_alloc_log SET row_count = 1 WHERE id = v_log_id;

    UPDATE batch_run
       SET status           = 'COMPLETED',
           source_row_count = v_src_count,
           output_row_count = v_debit_count + v_credit_count + v_orphan_count,
           orphan_count     = v_orphan_count,
           source_total     = v_src_total,
           output_total     = v_out_total,
           completed_at     = NOW()
     WHERE id = v_batch_id;

    -- ── Summary log row ──
    INSERT INTO sp_alloc_log (batch_id, phase, event_type, event_label, message)
    VALUES (v_batch_id, 9, 'SUMMARY', 'COMPLETED',
            format('debit=%s | credit=%s | orphan=%s | source_total=%s | output_total=%s | '
                   'variance=%s | source_rows=%s',
                   v_debit_count, v_credit_count, v_orphan_count,
                   round(v_src_total, 2), round(v_out_total, 2),
                   round(v_src_total - v_out_total, 2), v_src_count));

    RAISE NOTICE 'sp_run_allocation: COMPLETED — debit=%, credit=%, orphan=%, '
                 'source_total=%, output_total=%',
        v_debit_count, v_credit_count, v_orphan_count, v_src_total, v_out_total;

    EXCEPTION WHEN OTHERS THEN
        -- Mark batch as failed, log the error, and re-raise
        UPDATE batch_run
           SET status        = 'FAILED',
               error_message = SQLERRM,
               completed_at  = NOW()
         WHERE id = v_batch_id;

        -- Write error to sp_alloc_log (best-effort — ignore secondary failures)
        BEGIN
            INSERT INTO sp_alloc_log (batch_id, phase, event_type, event_label, message)
            VALUES (v_batch_id, 0, 'ERROR', 'EXCEPTION',
                    format('SQLERRM: %s  SQLSTATE: %s', SQLERRM, SQLSTATE));
        EXCEPTION WHEN OTHERS THEN
            NULL;  -- never let logging failure suppress the real exception
        END;

        RAISE NOTICE 'sp_run_allocation: FAILED — %', SQLERRM;
        RAISE;
    END;  -- nested error handler

END;
$$;

COMMENT ON PROCEDURE sp_run_allocation IS
    'Stored procedure version of the BankPFT allocation engine. '
    'Reads rule configuration from allocation_rule, joins source data with lookup ratios, '
    'and writes DEBIT/CREDIT entries to the output table. '
    'Supports RATIO, DISTRIBUTION, and STATIC methods with JSONB dimension mapping.';
