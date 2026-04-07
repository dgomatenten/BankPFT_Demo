-- ============================================================
-- 06_ftp.sql  —  Fund Transfer Pricing Tables
-- Tables: ref_interest_rate, ftp_product_config, ftp_run
-- ============================================================

-- ──────────────────────────────────────────────────────────
-- Interest rate curves (uploaded via Maker/Checker workflow)
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ref_interest_rate (
    id                   SERIAL        PRIMARY KEY,
    upload_batch_id      VARCHAR(36),
    effective_date       DATE          NOT NULL,
    interest_rate_code   VARCHAR(20)   NOT NULL,
    term                 INTEGER       NOT NULL,           -- numeric tenor value
    term_mult            VARCHAR(1)    NOT NULL,           -- D=day  M=month  Y=year
    rate                 NUMERIC(10,6) NOT NULL,           -- decimal, e.g. 0.05 = 5 %
    -- MakerCheckerMixin
    status               VARCHAR(20)   NOT NULL DEFAULT 'DRAFT',
    maker_id             VARCHAR(50)   NOT NULL,
    checker_id           VARCHAR(50),
    created_at           TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  ref_interest_rate                  IS 'Interest rate curve data used by the FTP moving-average engine.';
COMMENT ON COLUMN ref_interest_rate.interest_rate_code IS 'Rate curve identifier (e.g. SOFR, LIBOR, BBR). Must match ftp_product_config.rate_code.';
COMMENT ON COLUMN ref_interest_rate.term             IS 'Numeric tenor (e.g. 3 for a 3-month rate).';
COMMENT ON COLUMN ref_interest_rate.term_mult        IS 'Tenor multiplier: D = days, M = months, Y = years.';
COMMENT ON COLUMN ref_interest_rate.rate             IS 'Rate as a decimal fraction (0.05 = 5 %). Not a percentage.';

CREATE INDEX IF NOT EXISTS ix_ref_interest_rate_upload_batch_id    ON ref_interest_rate(upload_batch_id);
CREATE INDEX IF NOT EXISTS ix_ref_interest_rate_effective_date     ON ref_interest_rate(effective_date);
CREATE INDEX IF NOT EXISTS ix_ref_interest_rate_interest_rate_code ON ref_interest_rate(interest_rate_code);


-- ──────────────────────────────────────────────────────────
-- FTP calculation configuration per product
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ftp_product_config (
    id               SERIAL       PRIMARY KEY,
    product_code     VARCHAR(20)  NOT NULL UNIQUE REFERENCES dim_product(product_code),
    method           VARCHAR(20)  NOT NULL DEFAULT 'MOVING_AVG',  -- MOVING_AVG
    rate_code        VARCHAR(20)  NOT NULL,
    term             INTEGER      NOT NULL,
    term_mult        VARCHAR(1)   NOT NULL,                        -- D, M, Y
    avg_period       INTEGER      NOT NULL DEFAULT 1,
    avg_period_mult  VARCHAR(1)   NOT NULL DEFAULT 'M',            -- D, M, Y
    is_active        BOOLEAN      NOT NULL DEFAULT TRUE,
    created_by       VARCHAR(50),
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  ftp_product_config                IS 'FTP method and rate parameters per product code.';
COMMENT ON COLUMN ftp_product_config.method         IS 'Calculation method. Currently only MOVING_AVG is supported.';
COMMENT ON COLUMN ftp_product_config.avg_period     IS 'Moving-average lookback window length.';
COMMENT ON COLUMN ftp_product_config.avg_period_mult IS 'Lookback window unit: D=days, M=months, Y=years.';


-- ──────────────────────────────────────────────────────────
-- FTP run audit (one row per engine execution)
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ftp_run (
    id                     VARCHAR(36)  PRIMARY KEY,  -- UUID
    as_of_date             DATE         NOT NULL,
    status                 VARCHAR(20)  NOT NULL DEFAULT 'RUNNING',  -- RUNNING | COMPLETED | FAILED
    run_by                 VARCHAR(50),
    instruments_processed  INTEGER      NOT NULL DEFAULT 0,
    instruments_matched    INTEGER      NOT NULL DEFAULT 0,
    instruments_skipped    INTEGER      NOT NULL DEFAULT 0,
    started_at             TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    completed_at           TIMESTAMPTZ,
    error_message          TEXT
);

COMMENT ON TABLE  ftp_run                         IS 'Tracks each FTP engine execution — one row per batch run.';
COMMENT ON COLUMN ftp_run.instruments_matched     IS 'Instruments that had a matching FTP product config and rate.';
COMMENT ON COLUMN ftp_run.instruments_skipped     IS 'Instruments skipped due to missing product config or rate data.';
