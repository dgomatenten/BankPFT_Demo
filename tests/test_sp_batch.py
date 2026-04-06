"""Tests for the synchronous stored-procedure batch step integration.

Covers:
  - sp_runner.resolve_params — token substitution
  - sp_runner SP-name security validation (bad SP names rejected)
  - SpRun model creation
  - batch_executor CUSTOM_SP step → COMPLETED / FAILED status (synchronous)
  - SP run detail route
  - SP status JSON endpoint
"""

import json
import pytest
from datetime import date
from unittest.mock import patch, MagicMock


# ─────────────────────────────────────────────────────────────────────────────
# resolve_params — token substitution
# ─────────────────────────────────────────────────────────────────────────────

class TestResolveParams:
    def test_as_of_date_token(self):
        from app.services.sp_runner import resolve_params
        params = {"p_date": "{as_of_date}"}
        result = resolve_params(params, date(2026, 4, 6), "alice")
        assert result["p_date"] == "2026-04-06"

    def test_run_by_token(self):
        from app.services.sp_runner import resolve_params
        params = {"p_user": "{run_by}"}
        result = resolve_params(params, date(2026, 4, 6), "bob")
        assert result["p_user"] == "bob"

    def test_both_tokens_in_one_value(self):
        from app.services.sp_runner import resolve_params
        params = {"note": "run by {run_by} on {as_of_date}"}
        result = resolve_params(params, date(2026, 1, 31), "carol")
        assert result["note"] == "run by carol on 2026-01-31"

    def test_non_string_values_unchanged(self):
        from app.services.sp_runner import resolve_params
        params = {"threshold": 100, "active": True}
        result = resolve_params(params, date(2026, 4, 6), "alice")
        assert result["threshold"] == 100
        assert result["active"] is True

    def test_empty_params(self):
        from app.services.sp_runner import resolve_params
        assert resolve_params({}, date(2026, 4, 6), "alice") == {}


# ─────────────────────────────────────────────────────────────────────────────
# SP name validation security tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSpNameValidation:
    VALID_NAMES = [
        "sp_extract",
        "reporting_sp",
        "myschema.sp_month_end",
        "a",
        "Schema1.Proc_A",
    ]
    INVALID_NAMES = [
        "sp extract",            # space
        "sp-extract",            # hyphen
        "sp;drop table users",   # injection attempt
        "1sp_bad",               # starts with digit
        "sp.bad.extra",          # three-part name
        "",                      # empty
        "sp_name; SELECT 1",     # semicolon injection
        "schema.sp name",        # space after dot
    ]

    def test_valid_names_accepted(self, app):
        from app.services.sp_runner import run_sp
        for name in self.VALID_NAMES:
            with app.app_context():
                # Patch execute so no real DB call is made
                with patch("app.services.sp_runner.db.session.execute"):
                    with patch("app.services.sp_runner.db.session.commit"):
                        try:
                            sp_run = run_sp(name, {}, "alice")
                            assert sp_run.sp_name == name
                        except ValueError as e:
                            pytest.fail(f"Valid name '{name}' raised ValueError: {e}")

    def test_invalid_names_rejected(self, app):
        from app.services.sp_runner import run_sp
        for name in self.INVALID_NAMES:
            with app.app_context():
                with pytest.raises(ValueError, match="Invalid stored-procedure name"):
                    run_sp(name, {}, "alice")


# ─────────────────────────────────────────────────────────────────────────────
# SpRun model
# ─────────────────────────────────────────────────────────────────────────────

class TestSpRunModel:
    def test_create_sp_run(self, db_session, app):
        from app.models.workflow import SpRun
        with app.app_context():
            sp = SpRun(
                sp_name="reporting.sp_month_end",
                params_json={"p_date": "2026-04-06"},
                status="RUNNING",
                run_by="alice",
            )
            db_session.add(sp)
            db_session.flush()
            assert sp.id is not None
            assert sp.status == "RUNNING"
            assert sp.params_json["p_date"] == "2026-04-06"

    def test_sp_run_default_status(self, db_session, app):
        from app.models.workflow import SpRun
        with app.app_context():
            sp = SpRun(sp_name="dbo.sp_test", run_by="bob")
            db_session.add(sp)
            db_session.flush()
            assert sp.status == "RUNNING"

    def test_sp_run_link_to_exec_step(self, db_session, app):
        from app.models.workflow import SpRun, BatchDefinition, BatchTask, BatchExecution, BatchExecutionStep
        with app.app_context():
            defn = BatchDefinition(name="sp-test-defn", created_by="alice")
            db_session.add(defn)
            db_session.flush()

            task = BatchTask(
                definition_id=defn.id,
                step_order=1,
                task_type="CUSTOM_SP",
                ref_id="dbo.sp_test",
            )
            db_session.add(task)
            db_session.flush()

            execution = BatchExecution(
                definition_id=defn.id,
                as_of_date=date(2026, 4, 6),
                status="RUNNING",
                run_by="alice",
            )
            db_session.add(execution)
            db_session.flush()

            step = BatchExecutionStep(
                execution_id=execution.id,
                step_order=1,
                task_type="CUSTOM_SP",
                ref_id="dbo.sp_test",
                status="COMPLETED",
            )
            db_session.add(step)
            db_session.flush()

            sp = SpRun(
                sp_name="dbo.sp_test",
                status="COMPLETED",
                run_by="alice",
                exec_step_id=step.id,
            )
            db_session.add(sp)
            db_session.flush()

            assert sp.exec_step_id == step.id


# ─────────────────────────────────────────────────────────────────────────────
# batch_executor CUSTOM_SP synchronous execution
# ─────────────────────────────────────────────────────────────────────────────

class TestBatchExecutorCustomSp:
    def _make_defn_with_sp(self, db_session, sp_name="dbo.sp_ok", params=None):
        from app.models.workflow import BatchDefinition, BatchTask
        defn = BatchDefinition(name=f"sp-defn-{sp_name}", created_by="alice")
        db_session.add(defn)
        db_session.flush()
        task = BatchTask(
            definition_id=defn.id,
            step_order=1,
            task_type="CUSTOM_SP",
            ref_id=sp_name,
            label="Test SP step",
            params_json=params or {},
        )
        db_session.add(task)
        db_session.flush()
        return defn

    def test_sp_step_completed_synchronously(self, db_session, app):
        """A CUSTOM_SP step should run synchronously and become COMPLETED."""
        from app.services.batch_executor import run_batch
        with app.app_context():
            defn = self._make_defn_with_sp(db_session)
            # Patch execute so no real DB CALL is made
            with patch("app.services.sp_runner.db.session.execute"):
                execution = run_batch(defn.id, date(2026, 4, 6), "alice")

            assert execution.status == "COMPLETED"
            assert len(execution.steps) == 1
            step = execution.steps[0]
            assert step.status == "COMPLETED"
            assert step.ref_run_id is not None
            assert step.completed_at is not None

    def test_sp_step_params_copied_to_run(self, db_session, app):
        """params_json on the task should be resolved and carried onto the SpRun."""
        from app.services.batch_executor import run_batch
        from app.models.workflow import SpRun
        with app.app_context():
            defn = self._make_defn_with_sp(
                db_session,
                sp_name="dbo.sp_params",
                params={"p_date": "{as_of_date}"},
            )
            with patch("app.services.sp_runner.db.session.execute"):
                execution = run_batch(defn.id, date(2026, 4, 6), "alice")

            step = execution.steps[0]
            sp_run = db_session.get(SpRun, step.ref_run_id)
            assert sp_run is not None
            # Token should be resolved to the actual date string
            assert sp_run.params_json.get("p_date") == "2026-04-06"

    def test_invalid_sp_name_fails_step(self, db_session, app):
        """An invalid SP name (e.g. contains space) should fail the step."""
        from app.services.batch_executor import run_batch
        with app.app_context():
            defn = self._make_defn_with_sp(db_session, sp_name="bad sp name")
            execution = run_batch(defn.id, date(2026, 4, 6), "alice")

            assert execution.status in ("FAILED", "PARTIAL")
            step = execution.steps[0]
            assert step.status == "FAILED"
            assert "Invalid stored-procedure name" in (step.error_message or "")

    def test_sp_step_completed_at_set_after_run(self, db_session, app):
        """After synchronous execution, the step completed_at is set."""
        from app.services.batch_executor import run_batch
        with app.app_context():
            defn = self._make_defn_with_sp(db_session, sp_name="dbo.sp_timing")
            with patch("app.services.sp_runner.db.session.execute"):
                execution = run_batch(defn.id, date(2026, 4, 6), "alice")

            step = execution.steps[0]
            assert step.status == "COMPLETED"
            assert step.completed_at is not None


# ─────────────────────────────────────────────────────────────────────────────
# SP run detail route (drill-down from batch execution step)
# ─────────────────────────────────────────────────────────────────────────────

class TestSpDetailRoute:
    def test_detail_requires_login(self, client):
        rv = client.get("/batch/sp-runs/nonexistent-id", follow_redirects=False)
        assert rv.status_code in (302, 308)

    def test_detail_404_for_unknown_id(self, auth_client):
        rv = auth_client.get("/batch/sp-runs/00000000-0000-0000-0000-000000000000")
        assert rv.status_code == 404

    def test_detail_renders(self, auth_client, db_session):
        from app.models.workflow import SpRun
        sp = SpRun(
            sp_name="reporting.sp_detail_test",
            params_json={"p_date": "2026-04-06"},
            status="COMPLETED",
            run_by="alice",
            result_message="Done",
        )
        db_session.add(sp)
        db_session.commit()
        run_id = sp.id

        rv = auth_client.get(f"/batch/sp-runs/{run_id}")
        assert rv.status_code == 200
        assert b"reporting.sp_detail_test" in rv.data

    def test_detail_shows_params(self, auth_client, db_session):
        from app.models.workflow import SpRun
        sp = SpRun(
            sp_name="dbo.sp_params_display",
            params_json={"p_entity": "BRANCH-01", "p_user": "alice"},
            status="COMPLETED",
            run_by="alice",
        )
        db_session.add(sp)
        db_session.commit()
        run_id = sp.id

        rv = auth_client.get(f"/batch/sp-runs/{run_id}")
        assert rv.status_code == 200
        assert b"p_entity" in rv.data
        assert b"BRANCH-01" in rv.data


# ─────────────────────────────────────────────────────────────────────────────
# SP status JSON endpoint
# ─────────────────────────────────────────────────────────────────────────────

class TestSpStatusEndpoint:
    def test_status_requires_login(self, client):
        rv = client.get("/batch/sp-runs/some-id/status", follow_redirects=False)
        assert rv.status_code in (302, 308)

    def test_status_404_for_unknown(self, auth_client):
        rv = auth_client.get("/batch/sp-runs/00000000-dead-beef-cafe-000000000000/status")
        assert rv.status_code == 404

    def test_status_returns_json(self, auth_client, db_session):
        from app.models.workflow import SpRun
        sp = SpRun(sp_name="dbo.sp_poll", status="COMPLETED", run_by="alice")
        db_session.add(sp)
        db_session.commit()
        run_id = sp.id

        rv = auth_client.get(f"/batch/sp-runs/{run_id}/status")
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert data["id"] == run_id
        assert data["status"] == "COMPLETED"

    def test_status_json_fields_present(self, auth_client, db_session):
        from app.models.workflow import SpRun
        sp = SpRun(
            sp_name="dbo.sp_fields",
            status="FAILED",
            run_by="alice",
            error_message="SP not found",
        )
        db_session.add(sp)
        db_session.commit()
        run_id = sp.id

        rv = auth_client.get(f"/batch/sp-runs/{run_id}/status")
        data = json.loads(rv.data)
        assert "status" in data
        assert "completed_at" in data
        assert "result_message" in data
        assert "error_message" in data
        assert data["error_message"] == "SP not found"

