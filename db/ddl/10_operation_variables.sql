-- ============================================================
-- 10_operation_variables.sql  —  Operation Variables Table
-- Tables: operation_variable
-- ============================================================

CREATE TABLE IF NOT EXISTS operation_variable (
    id          SERIAL        PRIMARY KEY,
    key         VARCHAR(100)  NOT NULL UNIQUE,
    value       VARCHAR(500),
    description TEXT,
    data_type   VARCHAR(20)   NOT NULL DEFAULT 'string',  -- date | string | number
    is_system   BOOLEAN       NOT NULL DEFAULT FALSE,
    is_active   BOOLEAN       NOT NULL DEFAULT TRUE,
    updated_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_by  VARCHAR(50)
);

COMMENT ON TABLE  operation_variable             IS 'Named variables available to all batch engines at run time. Referenced as {key} tokens in batch task params_json.';
COMMENT ON COLUMN operation_variable.key         IS 'Unique identifier used as the {key} token in batch parameters. Letters, digits, underscores only.';
COMMENT ON COLUMN operation_variable.data_type   IS 'date: YYYY-MM-DD value  |  number: numeric string  |  string: free text.';
COMMENT ON COLUMN operation_variable.is_system   IS 'System variables are seeded automatically and cannot be deleted via the UI.';
COMMENT ON COLUMN operation_variable.is_active   IS 'Inactive variables are not resolved during token substitution.';

-- Seed the default processing_date variable
INSERT INTO operation_variable (key, value, description, data_type, is_system, is_active, updated_by)
VALUES (
    'processing_date',
    CURRENT_DATE::TEXT,
    'The current processing date used by batch engines. Update this to control which date is treated as ''today'' for all batch runs.',
    'date',
    TRUE,
    TRUE,
    'system'
)
ON CONFLICT (key) DO NOTHING;
