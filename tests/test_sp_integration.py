"""PostgreSQL integration tests for stored-procedure execution.

These tests require a live PostgreSQL instance and are skipped automatically
when DATABASE_URL is unset or does not point to a postgresql:// server.

Run against the dev Docker DB:

    DATABASE_URL="postgresql://bankpft:bankpft_dev@localhost:5432/bankpft" \\
        python -m pytest tests/test_sp_integration.py -v -m integration

The session fixture ``pg_db_objects`` creates:
  - ``sp_call_log`` table     (from db/ddl/sp_call_log.sql)
  - ``sp_test_echo`` procedure (from db/procedures/sp_test_echo.sql)

Both objects are dropped at the end of the test session.
"""

import os
import pytest
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parent.parent


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _pg_url() -> str | None:
    url = os.getenv("DATABASE_URL", "")
    return url if url.startswith("postgresql") else None


# ─────────────────────────────────────────────────────────────────────────────
# Session-scoped fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def pg_url():
    """Resolve DATABASE_URL; skip the whole session if not PostgreSQL."""
    url = _pg_url()
    if not url:
        pytest.skip(
            "PostgreSQL not available — set DATABASE_URL to a postgresql:// URL "
            "before running integration tests."
        )
    return url


@pytest.fixture(scope="session")
def pg_engine(pg_url):
    """Raw SQLAlchemy engine for DDL setup and direct verification queries."""
    engine = create_engine(pg_url, future=True)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"Cannot connect to PostgreSQL: {exc}")
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def pg_app(pg_url):
    """Flask application wired to the dev PostgreSQL instance."""
    from app import create_app
    from app.config import Config
    from app.models import db as _db

    class PgTestConfig(Config):
        TESTING = True
        SQLALCHEMY_DATABASE_URI = pg_url
        WTF_CSRF_ENABLED = False
        SECRET_KEY = "integration-test-key"

    flask_app = create_app(PgTestConfig)
    with flask_app.app_context():
        _db.create_all()
    yield flask_app


@pytest.fixture(scope="session")
def pg_db_objects(pg_engine):
    """Create test DDL objects once per session; drop them at teardown.

    Objects created:
      - sp_call_log table  (db/ddl/sp_call_log.sql)
      - sp_test_echo proc  (db/procedures/sp_test_echo.sql)
    """
    ddl_sql = (REPO_ROOT / "db" / "ddl" / "sp_call_log.sql").read_text()
    proc_sql = (REPO_ROOT / "db" / "procedures" / "sp_test_echo.sql").read_text()

    with pg_engine.begin() as conn:
        conn.execute(text(ddl_sql))
        conn.execute(text(proc_sql))

    yield  # ← tests execute here

    with pg_engine.begin() as conn:
        conn.execute(text("DROP PROCEDURE IF EXISTS sp_test_echo(TEXT, TEXT)"))
        conn.execute(text("DROP TABLE IF EXISTS sp_call_log"))


# ─────────────────────────────────────────────────────────────────────────────
# Tests: DDL / direct CALL verification (no Flask, no dispatch_sp)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.integration
class TestSpTestEchoProcedure:
    """Verify the test SP and its audit table exist and work correctly."""

    def test_sp_test_echo_exists_in_catalog(self, pg_engine, pg_db_objects):
        """sp_test_echo should appear in pg_catalog.pg_proc."""
        with pg_engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT proname FROM pg_catalog.pg_proc "
                    "WHERE proname = 'sp_test_echo'"
                )
            ).fetchone()
        assert row is not None, "sp_test_echo not found in pg_catalog.pg_proc"

    def test_sp_call_log_table_exists(self, pg_engine, pg_db_objects):
        """sp_call_log should appear in information_schema.tables."""
        with pg_engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_name = 'sp_call_log'"
                )
            ).fetchone()
        assert row is not None, "sp_call_log table not found"

    def test_direct_call_writes_log_row(self, pg_engine, pg_db_objects):
        """A direct CALL sp_test_echo should insert one row into sp_call_log."""
        with pg_engine.connect() as conn:
            before = conn.execute(
                text("SELECT COUNT(*) FROM sp_call_log")
            ).scalar()

        with pg_engine.begin() as conn:
            conn.execute(
                text("CALL sp_test_echo(:p_as_of_date, :p_run_by)"),
                {"p_as_of_date": "2026-04-06", "p_run_by": "direct_call_test"},
            )

        with pg_engine.connect() as conn:
            after = conn.execute(
                text("SELECT COUNT(*) FROM sp_call_log")
            ).scalar()

        assert after == before + 1

    def test_direct_call_stores_correct_values(self, pg_engine, pg_db_objects):
        """called_by and as_of_date should be stored as passed."""
        with pg_engine.begin() as conn:
            conn.execute(
                text("CALL sp_test_echo(:p_as_of_date, :p_run_by)"),
                {"p_as_of_date": "2026-01-31", "p_run_by": "value_verify"},
            )

        with pg_engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT called_by, as_of_date "
                    "FROM sp_call_log "
                    "WHERE called_by = 'value_verify' "
                    "ORDER BY called_at DESC LIMIT 1"
                )
            ).fetchone()

        assert row is not None
        assert row[0] == "value_verify"
        assert str(row[1]) == "2026-01-31"

    def test_direct_call_null_params_accepted(self, pg_engine, pg_db_objects):
        """sp_test_echo should accept NULL for both parameters."""
        with pg_engine.begin() as conn:
            conn.execute(
                text("CALL sp_test_echo(:p_as_of_date, :p_run_by)"),
                {"p_as_of_date": None, "p_run_by": None},
            )

        with pg_engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT id FROM sp_call_log "
                    "WHERE called_by IS NULL AND as_of_date IS NULL "
                    "ORDER BY called_at DESC LIMIT 1"
                )
            ).fetchone()

        assert row is not None, "NULL-param call did not write a log row"


# ─────────────────────────────────────────────────────────────────────────────
# Tests: full end-to-end via run_sp (Flask app, synchronous)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.integration
class TestRunSpEndToEnd:
    """Verify the synchronous run_sp pipeline against real PostgreSQL."""

    def test_run_sp_creates_sp_run_record_completed(self, pg_app, pg_engine, pg_db_objects):
        """run_sp should create a SpRun row and return it with status COMPLETED."""
        from app.services.sp_runner import run_sp

        with pg_app.app_context():
            sp_run = run_sp(
                sp_name="sp_test_echo",
                params={"p_as_of_date": "2026-04-06", "p_run_by": "run_sp_create"},
                run_by="run_sp_create",
                exec_step_id=None,
                app_or_session=None,
            )
            run_id = sp_run.id
            final_status = sp_run.status

        assert final_status == "COMPLETED", f"Expected COMPLETED, got {final_status}"

        with pg_engine.connect() as conn:
            row = conn.execute(
                text("SELECT status FROM sp_run WHERE id = :id"),
                {"id": run_id},
            ).fetchone()

        assert row is not None, "SpRun row not found after run_sp"
        assert row[0] == "COMPLETED"

    def test_run_sp_completes_with_status_completed(self, pg_app, pg_engine, pg_db_objects):
        """run_sp should return COMPLETED synchronously."""
        from app.services.sp_runner import run_sp

        with pg_app.app_context():
            sp_run = run_sp(
                sp_name="sp_test_echo",
                params={"p_as_of_date": "2026-04-06", "p_run_by": "e2e_completed"},
                run_by="e2e_completed",
                exec_step_id=None,
                app_or_session=None,
            )

        assert sp_run.status == "COMPLETED", (
            f"Expected COMPLETED, got {sp_run.status}. Error: {sp_run.error_message}"
        )

    def test_run_sp_writes_audit_row(self, pg_app, pg_engine, pg_db_objects):
        """The SP called via run_sp should write a row into sp_call_log."""
        from app.services.sp_runner import run_sp

        run_by_marker = "e2e_audit_check"

        with pg_engine.connect() as conn:
            before = conn.execute(
                text("SELECT COUNT(*) FROM sp_call_log WHERE called_by = :u"),
                {"u": run_by_marker},
            ).scalar()

        with pg_app.app_context():
            run_sp(
                sp_name="sp_test_echo",
                params={"p_as_of_date": "2026-04-06", "p_run_by": run_by_marker},
                run_by=run_by_marker,
                exec_step_id=None,
                app_or_session=None,
            )

        with pg_engine.connect() as conn:
            after = conn.execute(
                text("SELECT COUNT(*) FROM sp_call_log WHERE called_by = :u"),
                {"u": run_by_marker},
            ).scalar()

        assert after == before + 1, (
            f"Expected sp_call_log to gain 1 row, was {before} now {after}"
        )

    def test_run_sp_completed_at_is_set(self, pg_app, pg_engine, pg_db_objects):
        """SpRun.completed_at should be set when run_sp returns."""
        from app.services.sp_runner import run_sp

        with pg_app.app_context():
            sp_run = run_sp(
                sp_name="sp_test_echo",
                params={"p_as_of_date": "2026-04-06", "p_run_by": "e2e_timing"},
                run_by="e2e_timing",
                exec_step_id=None,
                app_or_session=None,
            )
            run_id = sp_run.id

        with pg_engine.connect() as conn:
            row = conn.execute(
                text("SELECT completed_at FROM sp_run WHERE id = :id"),
                {"id": run_id},
            ).fetchone()

        assert row is not None
        assert row[0] is not None, "completed_at should not be NULL after COMPLETED"

    def test_run_sp_invalid_name_raises_value_error(self, pg_app, pg_db_objects):
        """run_sp with a bad name must raise ValueError before touching the DB."""
        from app.services.sp_runner import run_sp

        with pg_app.app_context():
            with pytest.raises(ValueError, match="Invalid stored-procedure name"):
                run_sp(
                    sp_name="bad sp name; DROP TABLE sp_run",
                    params={},
                    run_by="security_test",
                    exec_step_id=None,
                    app_or_session=None,
                )

    def test_run_sp_nonexistent_sp_sets_failed(self, pg_app, pg_engine, pg_db_objects):
        """Calling a non-existent procedure should result in SpRun status=FAILED."""
        from app.services.sp_runner import run_sp

        with pg_app.app_context():
            sp_run = run_sp(
                sp_name="sp_does_not_exist_bankpft_xyz",
                params={},
                run_by="e2e_fail_test",
                exec_step_id=None,
                app_or_session=None,
            )

        assert sp_run.status == "FAILED", f"Expected FAILED, got {sp_run.status}"
        assert sp_run.error_message, "error_message should be set for a FAILED SpRun"

        with pg_engine.connect() as conn:
            row = conn.execute(
                text("SELECT status, error_message FROM sp_run WHERE id = :id"),
                {"id": sp_run.id},
            ).fetchone()

        assert row is not None
        assert row[0] == "FAILED"
        assert row[1]

    def test_run_sp_token_resolution_visible_in_call_log(
        self, pg_app, pg_engine, pg_db_objects
    ):
        """Token {as_of_date} resolved by batch_executor should appear correctly."""
        from app.services.sp_runner import run_sp, resolve_params

        as_of = date(2026, 3, 31)
        resolved = resolve_params(
            {"p_as_of_date": "{as_of_date}", "p_run_by": "{run_by}"},
            as_of,
            "token_tester",
        )

        with pg_app.app_context():
            sp_run = run_sp(
                sp_name="sp_test_echo",
                params=resolved,
                run_by="token_tester",
                exec_step_id=None,
                app_or_session=None,
            )

        assert sp_run.status == "COMPLETED"

        with pg_engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT called_by, as_of_date FROM sp_call_log "
                    "WHERE called_by = 'token_tester' "
                    "ORDER BY called_at DESC LIMIT 1"
                )
            ).fetchone()

        assert row is not None
        assert row[0] == "token_tester"
        assert str(row[1]) == "2026-03-31"
