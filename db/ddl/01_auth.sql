-- ============================================================
-- 01_auth.sql  —  Authentication & User Management
-- Tables: "group", "user", user_group
--
-- Note: "group" and "user" are reserved words in PostgreSQL and
-- must be quoted everywhere they appear.
-- ============================================================

CREATE TABLE IF NOT EXISTS "group" (
    id          SERIAL        PRIMARY KEY,
    name        VARCHAR(80)   NOT NULL UNIQUE,
    description VARCHAR(200),
    can_make    BOOLEAN       NOT NULL DEFAULT FALSE,
    can_check   BOOLEAN       NOT NULL DEFAULT FALSE,
    is_admin    BOOLEAN       NOT NULL DEFAULT FALSE,
    is_active   BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  "group"             IS 'Application permission groups (Maker / Checker / Admin).';
COMMENT ON COLUMN "group".can_make    IS 'Members of this group may submit (make) upload batches.';
COMMENT ON COLUMN "group".can_check   IS 'Members of this group may approve/reject (check) upload batches.';
COMMENT ON COLUMN "group".is_admin    IS 'Members of this group have full administrative access.';


CREATE TABLE IF NOT EXISTS "user" (
    id            SERIAL        PRIMARY KEY,
    username      VARCHAR(80)   NOT NULL UNIQUE,
    display_name  VARCHAR(120),
    password_hash VARCHAR(256)  NOT NULL,
    is_active     BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  "user"              IS 'Application users. Passwords stored as Werkzeug pbkdf2 hashes.';
COMMENT ON COLUMN "user".password_hash IS 'Werkzeug generate_password_hash output — never store plain text.';


CREATE TABLE IF NOT EXISTS user_group (
    user_id  INTEGER NOT NULL REFERENCES "user"("id")  ON DELETE CASCADE,
    group_id INTEGER NOT NULL REFERENCES "group"("id") ON DELETE CASCADE,
    PRIMARY KEY (user_id, group_id)
);

COMMENT ON TABLE user_group IS 'Many-to-many join between users and permission groups.';
