"""Stored-procedure runner — fires CUSTOM_SP batch steps asynchronously.

A background thread calls the PostgreSQL stored procedure via
``CALL sp_name(:p1, :p2, ...)``, then updates the SpRun record when done.
The batch executor does NOT wait; it marks the step DISPATCHED and moves on.

Security:
  - SP names are validated against a strict identifier pattern before use.
  - All parameters are passed as named bind variables, never interpolated.

Supported runtime substitution tokens in params_json values:
  ``{as_of_date}``  →  the batch as-of date (ISO string)
  ``{run_by}``      →  username of the triggering user
"""
from __future__ import annotations

import re
import threading
import uuid
from datetime import date

from sqlalchemy import text

from app.core.time_utils import utc_now
from app.models import db
from app.models.workflow import SpRun

# Only allow safe SQL identifiers: optional schema prefix, then identifier chars.
_SP_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)?$")


def dispatch_sp(
    sp_name: str,
    params: dict,
    run_by: str,
    exec_step_id: int | None,
    app,
) -> SpRun:
    """Create a SpRun record and fire the SP in a background daemon thread.

    Returns the SpRun immediately (status=RUNNING).  The caller should store
    ``sp_run.id`` on the BatchExecutionStep so the monitoring screen can link
    back to it.
    """
    if not _SP_NAME_RE.match(sp_name):
        raise ValueError(
            f"Invalid stored-procedure name '{sp_name}'. "
            "Use only letters, digits, underscores and an optional schema prefix."
        )

    sp_run = SpRun(
        id=str(uuid.uuid4()),
        sp_name=sp_name,
        params_json=params or {},
        status="RUNNING",
        run_by=run_by,
        exec_step_id=exec_step_id,
    )
    db.session.add(sp_run)
    db.session.commit()

    thread = threading.Thread(
        target=_execute_sp,
        args=(sp_run.id, sp_name, params, app),
        daemon=True,
    )
    thread.start()

    return sp_run


def _execute_sp(sp_run_id: str, sp_name: str, params: dict, app) -> None:
    """Run inside a background thread — calls the SP and updates SpRun status."""
    with app.app_context():
        sp_run = db.session.get(SpRun, sp_run_id)
        if sp_run is None:
            return  # should never happen

        try:
            # Build parameterised CALL statement
            if params:
                placeholders = ", ".join(f":{k}" for k in params)
                sql = f"CALL {sp_name}({placeholders})"
            else:
                sql = f"CALL {sp_name}()"

            db.session.execute(text(sql), params)
            db.session.commit()

            sp_run.status = "COMPLETED"
            sp_run.result_message = "Stored procedure executed successfully."
        except Exception as exc:
            db.session.rollback()
            sp_run.status = "FAILED"
            sp_run.error_message = str(exc)
        finally:
            sp_run.completed_at = utc_now()
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()


def resolve_params(params: dict, as_of_date: date, run_by: str) -> dict:
    """Replace ``{as_of_date}`` and ``{run_by}`` tokens in parameter values."""
    resolved = {}
    for k, v in params.items():
        if isinstance(v, str):
            v = v.replace("{as_of_date}", as_of_date.isoformat())
            v = v.replace("{run_by}", run_by)
        resolved[k] = v
    return resolved
