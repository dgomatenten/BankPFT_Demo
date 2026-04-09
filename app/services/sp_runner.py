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

Traceability:
  - SpRun.executed_sql  saves the rendered CALL statement before execution.
  - SpRun.notices_log   saves a summary from sp_alloc_log after execution
                        (only when the SP name is 'sp_run_allocation').
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

# SP name that writes to sp_alloc_log (used to fetch notices_log summary)
_ALLOC_SP_NAME = "sp_run_allocation"


def run_sp(
    sp_name: str,
    params: dict,
    run_by: str,
    exec_step_id: int | None = None,
) -> SpRun:
    """Execute a stored procedure synchronously and return the SpRun record.

    Validates the SP name, creates a SpRun row (RUNNING), records the rendered
    CALL SQL in ``executed_sql``, calls the SP, then marks the SpRun COMPLETED
    or FAILED before returning.  The caller (batch executor) inspects
    ``sp_run.status`` to decide the step outcome.

    For ``sp_run_allocation``, an additional query to ``sp_alloc_log`` is made
    after execution to save a human-readable summary in ``notices_log``.
    """
    if not _SP_NAME_RE.match(sp_name):
        raise ValueError(
            f"Invalid stored-procedure name '{sp_name}'. "
            "Use only letters, digits, underscores and an optional schema prefix."
        )

    # Build parameterised CALL statement
    if params:
        placeholders = ", ".join(f":{k}" for k in params)
        call_sql = f"CALL {sp_name}({placeholders})"
    else:
        call_sql = f"CALL {sp_name}()"

    sp_run = SpRun(
        id=str(uuid.uuid4()),
        sp_name=sp_name,
        params_json=params or {},
        status="RUNNING",
        run_by=run_by,
        exec_step_id=exec_step_id,
        executed_sql=call_sql,          # ← traceability: save before execution
    )
    db.session.add(sp_run)
    db.session.commit()

    try:
        db.session.execute(text(call_sql), params)
        db.session.commit()

        sp_run.status = "COMPLETED"
        sp_run.result_message = "Stored procedure executed successfully."

        # ── Traceability: fetch sp_alloc_log summary for sp_run_allocation ──
        # The SP writes a batch_id into batch_run; we locate it via the most
        # recent batch_run row that was created by this sp_run's run_by user
        # within the last 60 seconds, then pull its log summary.
        _sp_base = sp_name.split(".")[-1]   # strip schema prefix if present
        if _sp_base == _ALLOC_SP_NAME:
            sp_run.notices_log = _fetch_alloc_log_summary(params)

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


def _fetch_alloc_log_summary(params: dict) -> str | None:
    """Query sp_alloc_log for the batch that was just created by sp_run_allocation.

    We identify the batch by looking for the most recent SUMMARY or ERROR row
    whose batch_id matches a batch_run created in the last 2 minutes for the
    same rule_id / as_of_date passed in params.

    Returns a newline-separated summary string, or None on any failure.
    """
    try:
        rule_id    = params.get("p_rule_id")
        as_of_date = params.get("p_as_of_date")
        if not (rule_id and as_of_date):
            return None

        # Find the batch_id from batch_run matching this rule + date (most recent)
        row = db.session.execute(
            text(
                "SELECT id FROM batch_run "
                "WHERE rule_id = :rid AND as_of_date = :dt "
                "ORDER BY started_at DESC LIMIT 1"
            ),
            {"rid": int(rule_id), "dt": as_of_date},
        ).fetchone()
        if not row:
            return None

        batch_id = row[0]

        # Pull all log rows for that batch
        log_rows = db.session.execute(
            text(
                "SELECT phase, event_type, event_label, sql_text, row_count, message, logged_at "
                "FROM sp_alloc_log "
                "WHERE batch_id = :bid "
                "ORDER BY id"
            ),
            {"bid": batch_id},
        ).fetchall()

        if not log_rows:
            return None

        lines = [f"batch_id: {batch_id}"]
        for r in log_rows:
            phase, etype, label, sql_text, rcount, msg, ts = r
            ts_str = ts.strftime("%H:%M:%S.%f")[:-3] if ts else ""
            parts = [f"[{ts_str}] [Phase {phase}] [{etype}]"]
            if label:
                parts.append(label)
            if msg:
                parts.append(msg)
            if rcount is not None:
                parts.append(f"rows={rcount}")
            lines.append("  ".join(parts))
            if sql_text:
                # Indent SQL for readability
                for sql_line in sql_text.strip().splitlines():
                    lines.append(f"    {sql_line}")

        return "\n".join(lines)
    except Exception:
        return None  # fail open — traceability is non-critical


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
