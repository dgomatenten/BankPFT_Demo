-- Alert Configurations
-- Stores user-defined dashboard alert rules evaluated on every page load.
-- check_type: 'table_row_check' (only supported type currently)

CREATE TABLE alert_config (
    id           SERIAL PRIMARY KEY,
    name         VARCHAR(100)  NOT NULL,
    description  TEXT,
    check_type   VARCHAR(30)   NOT NULL DEFAULT 'table_row_check',
    table_name   VARCHAR(100),
    date_column  VARCHAR(100),
    severity     VARCHAR(20)   NOT NULL DEFAULT 'warning',
    is_active    BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    created_by   VARCHAR(50)
);

CREATE INDEX idx_alert_config_active ON alert_config (is_active);
