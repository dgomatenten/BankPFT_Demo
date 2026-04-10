"""FTP engine, config CRUD, and batch/datafile service tests."""

import json
import pytest
from datetime import date, timedelta


# ─────────────────────────────────────────────────────────────────────────────
# FTP product config model
# ─────────────────────────────────────────────────────────────────────────────

class TestFtpModels:
    def test_create_model(self, db_session, app):
        from app.models.ftp import FtpModel, FtpModelRule, FtpProcess
        with app.app_context():
            model = FtpModel(model_name="TEST_MODEL_X", is_active=True)
            db_session.add(model)
            db_session.flush()
            assert model.id is not None
            
            rule = FtpModelRule(
                ftp_model_id=model.id,
                product_code="TEST-LON",
                rate_code="SWAP_RATE",
                term=3,
                term_mult="M",
                lp_rate=0.015
            )
            db_session.add(rule)
            
            proc = FtpProcess(
                process_name="TEST_PROC_X",
                ftp_model_id=model.id,
            )
            db_session.add(proc)
            db_session.flush()
            
            assert rule.id is not None
            assert proc.id is not None


# ─────────────────────────────────────────────────────────────────────────────
# FTP config UI routes
# ─────────────────────────────────────────────────────────────────────────────

class TestFtpRoutes:
    def test_ftp_index_requires_login(self, client):
        rv = client.get("/ftp/", follow_redirects=False)
        assert rv.status_code in (302, 308)

    def test_ftp_index_renders(self, auth_client):
        rv = auth_client.get("/ftp/")
        assert rv.status_code == 200

    def test_model_list_renders(self, auth_client):
        rv = auth_client.get("/ftp/models")
        assert rv.status_code == 200

    def test_process_list_renders(self, auth_client):
        rv = auth_client.get("/ftp/processes")
        assert rv.status_code == 200

    def test_model_new_renders(self, auth_client):
        rv = auth_client.get("/ftp/models/new")
        assert rv.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# FTP engine lookback helper
# ─────────────────────────────────────────────────────────────────────────────

class TestLookbackStart:
    def test_day_lookback(self, app):
        from app.services.ftp_engine import _lookback_start
        with app.app_context():
            result = _lookback_start(date(2026, 3, 15), 10, "D")
            assert result == date(2026, 3, 5)

    def test_month_lookback(self, app):
        from app.services.ftp_engine import _lookback_start
        with app.app_context():
            result = _lookback_start(date(2026, 3, 31), 1, "M")
            assert result == date(2026, 2, 28)

    def test_month_lookback_across_year(self, app):
        from app.services.ftp_engine import _lookback_start
        with app.app_context():
            result = _lookback_start(date(2026, 2, 15), 3, "M")
            assert result == date(2025, 11, 15)

    def test_year_lookback(self, app):
        from app.services.ftp_engine import _lookback_start
        with app.app_context():
            result = _lookback_start(date(2026, 6, 30), 1, "Y")
            assert result == date(2025, 6, 30)


# ─────────────────────────────────────────────────────────────────────────────
# FTP engine — end-to-end
# ─────────────────────────────────────────────────────────────────────────────

class TestFtpEngine:
    def test_run_ftp_returns_run_record(self, seeded_db, app):
        from app.services.ftp_engine import run_ftp
        from app.models.ftp import FtpProcess
        with app.app_context():
            process_id = FtpProcess.query.first().id
            ftp_run = run_ftp(process_id, date(2026, 1, 1), "admin")
            assert ftp_run is not None
            assert ftp_run.status == "COMPLETED"

    def test_run_ftp_matches_instrument_with_config(self, seeded_db, app):
        from app.services.ftp_engine import run_ftp
        from app.models.ftp import FtpProcess
        with app.app_context():
            process_id = FtpProcess.query.first().id
            ftp_run = run_ftp(process_id, date(2026, 1, 1), "admin")
            assert ftp_run.instruments_processed >= 1
            assert ftp_run.instruments_matched >= 1

    def test_run_ftp_writes_base_rate_and_lp(self, seeded_db, app):
        from app.services.ftp_engine import run_ftp
        from app.models.staging import ProcInstData
        from app.models.ftp import FtpProcess
        with app.app_context():
            process_id = FtpProcess.query.first().id
            run_ftp(process_id, date(2026, 1, 1), "admin")
            inst = ProcInstData.query.filter_by(as_of_date=date(2026, 1, 1)).first()
            if inst:
                assert inst.base_rate is not None
                assert inst.cost_of_fund is not None
                assert inst.cost_of_fund > 0
                assert inst.lp_rate is not None
                assert inst.clp_rate is not None

    def test_run_ftp_no_instruments_completes_clean(self, db_session, app, seeded_db):
        """FTP run with no instruments should complete without error."""
        from app.services.ftp_engine import run_ftp
        from app.models.ftp import FtpProcess
        with app.app_context():
            process_id = FtpProcess.query.first().id
            ftp_run = run_ftp(process_id, date(2099, 12, 31), "admin")
            assert ftp_run.status == "COMPLETED"
            assert ftp_run.instruments_processed == 0


# ─────────────────────────────────────────────────────────────────────────────
# Batch definitions
# ─────────────────────────────────────────────────────────────────────────────

class TestBatchDefinition:
    def test_definition_model_create(self, db_session, app):
        from app.models.workflow import BatchDefinition, BatchTask
        with app.app_context():
            defn = BatchDefinition(
                name="Test Batch",
                description="Test",
                created_by="admin",
                is_active=True,
            )
            db_session.add(defn)
            db_session.flush()
            assert defn.id is not None

    def test_definition_list_requires_auth(self, client):
        rv = client.get("/batch/definitions", follow_redirects=False)
        assert rv.status_code in (302, 308)

    def test_definition_list_renders(self, auth_client):
        rv = auth_client.get("/batch/definitions")
        assert rv.status_code == 200

    def test_definition_new_form_renders(self, auth_client):
        rv = auth_client.get("/batch/definitions/new")
        assert rv.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# Datafile service — config loading
# ─────────────────────────────────────────────────────────────────────────────

class TestDatafileConfig:
    def test_datafile_config_has_formats(self, app):
        from app.services.datafile_service import DATAFILE_CONFIG
        with app.app_context():
            assert "formats" in DATAFILE_CONFIG
            assert len(DATAFILE_CONFIG["formats"]) > 0

    def test_all_formats_have_format_id(self, app):
        from app.services.datafile_service import DATAFILE_CONFIG
        with app.app_context():
            for fmt in DATAFILE_CONFIG.get("formats", []):
                assert "format_id" in fmt, f"Missing format_id in {fmt}"

    def test_datafile_config_has_exports(self, app):
        from app.services.datafile_service import DATAFILE_CONFIG
        with app.app_context():
            assert "exports" in DATAFILE_CONFIG
            assert len(DATAFILE_CONFIG["exports"]) > 0

    def test_import_nonexistent_format_raises(self, db_session, app):
        from app.services.datafile_service import import_file
        with app.app_context():
            with pytest.raises(ValueError):
                import_file("NONEXISTENT_FORMAT_XYZ", "file.dat", "admin")
