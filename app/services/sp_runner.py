"""Stored-procedure runner — executes CUSTOM_SP batch steps synchronously.

The batch executor calls ``run_sp()`` which executes the stored procedure in
the current thread (same as ALLOCATION / FTP / DATAFILE steps) and returns
a completed SpRun record.

Security:
  - SP names are validated against a strict identifier pattern before use.
  - All parameters are passed as named bind variables, never interpolated.

Supported runtime substitution tokens in params_json values:
  ``{as_of_date}``  →  the batch as-of date (ISO string)
  ``{run_by}``      →  username of the triggering user
"""
from __future__ import annotations

import re
import uuid
from datetime import date

from sqlalchemy import text

from app.core.time_utils import utc_now
from app.models import db
from app.models.workflow import SpRun

# Only allow safe SQL identifiers: optional schema prefix, then identifier chars.
_SP_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)?$")


def run_sp(
    sp_name: str,
    params: dict,
    run_by: str,
    exec_step_id: int | None = None,
) -> SpRun:
    """Execute a stored procedure synchronously and return the SpRun record.

    Validates the SP name, creates a SpRun row (RUNNING), calls the SP,
    then marks the SpRun COMPLETED or FAILED before returning.  The caller
    (batch executor) inspects ``sp_run.status`` to decide the step outcome.
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

    return sp_run


def resolve_params(params: dict, as_of_date: date, run_by: str) -> dict:
    """Replace ``{as_of_date}``, ``{run_by}``, and any ``{op_var_key}`` tokens
    in parameter values.

    Operation variables are loaded from the database (active rows only). The
    built-in tokens ``{as_of_date}`` and ``{run_by}`` take precedence over any
    operation variable with the same key.
    """
    from app.models.workflow import OperationVariable

    # Build substitution map from DB operation variables (active only)
    token_map: dict[str, str] = {}
    try:
        for v in OperationVariable.query.filter_by(is_active=True).all():
            if v.value is not None:
                token_map[v.key] = v.value
    except Exception:
        pass  # Fail open — DB may not be ready during tests

    # Built-in tokens always override
    token_map["as_of_date"] = as_of_date.isoformat()
    token_map["run_by"] = run_by

    resolved = {}
    for k, v in params.items():
        if isinstance(v, str):
            for token_key, token_val in token_map.items():
                v = v.replace(f"{{{token_key}}}", token_val)
        resolved[k] = v
    return resolved

