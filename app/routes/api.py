"""REST API blueprint — /api/v1/

Authentication: HTTP Basic Auth using existing user accounts.
All responses are JSON. Errors use { "error": "message" }.

Endpoints
---------
POST /api/v1/datafile/import
    body: { "format_id": "LOAN_FIXED", "filename": "loan.dat" }
    → { "batch_id", "status", "row_count", "error_count", "target_table", "started_at", "completed_at" }

POST /api/v1/datafile/export
    body: { "export_id": "ALLOC_RESULT_EXPORT", "as_of_date": "2026-01-01" }
    → { "batch_id", "status", "row_count", "filename", "started_at", "completed_at" }

GET  /api/v1/datafile/batch/<batch_id>
    → datafile batch status + errors

POST /api/v1/batch/allocation
    body: { "rule_id": 1, "as_of_date": "2026-01-01" }
    → { "batch_id", "status", "source_row_count", "output_row_count", ... }

GET  /api/v1/batch/allocation/<batch_id>
    → allocation batch status

POST /api/v1/batch/ftp
    body: { "as_of_date": "2026-01-01" }
    → { "run_id", "status", "instruments_processed", "instruments_matched", ... }

GET  /api/v1/batch/ftp/<run_id>
    → FTP run status

GET  /api/v1/datafile/formats
    → list of available import formats

GET  /api/v1/datafile/exports
    → list of available export configs

GET  /api/v1/batch/rules
    → list of active allocation rules

GET  /api/v1/batch/definitions
    → list of active multi-task batch definitions (with step counts)

GET  /api/v1/batch/definitions/<def_id>
    → single definition with ordered step list

POST /api/v1/batch/definitions/<def_id>/run
    body: { "as_of_date": "2026-01-01" }   (date is optional, defaults to today)
    → { "execution_id", "definition_id", "definition_name", "status", "steps": [...], ... }

GET  /api/v1/batch/executions/<exec_id>
    → full execution record with per-step results
"""

import json
from datetime import date, datetime
from functools import wraps

from flask import Blueprint, jsonify, request

from app.models.auth import User
from app.models.datafile import DataFileBatch
from app.models.workflow import AllocationRule, BatchRun, BatchDefinition, BatchExecution, BatchExecutionStep
from app.models.ftp import FtpRun
from app.services.datafile_service import (
    DATAFILE_CONFIG, import_file, export_data,
)
from app.services.allocation_engine import run_allocation
from app.services.ftp_engine import run_ftp
from app.services.batch_executor import run_batch

bp = Blueprint("api", __name__)


# ── Authentication ────────────────────────────────────────────────────────────

def _authenticate() -> User | None:
    """Validate HTTP Basic Auth credentials. Returns User or None."""
    auth = request.authorization
    if not auth or not auth.username or not auth.password:
        return None
    user = User.query.filter_by(username=auth.username, is_active=True).first()
    if user and user.check_password(auth.password):
        return user
    return None


def api_login_required(f):
    """Decorator: require valid HTTP Basic Auth, inject `api_user` kwarg."""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = _authenticate()
        if user is None:
            return (
                jsonify({"error": "Unauthorized — provide valid credentials via HTTP Basic Auth"}),
                401,
                {"WWW-Authenticate": 'Basic realm="BankPFT API"'},
            )
        return f(*args, api_user=user, **kwargs)
    return decorated


# ── Serialisers ───────────────────────────────────────────────────────────────

def _fmt_dt(dt) -> str | None:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None


def _datafile_batch_dict(b: DataFileBatch) -> dict:
    return {
        "batch_id":    b.id,
        "operation":   b.operation,
        "format_id":   b.format_id,
        "format_name": b.format_name,
        "filename":    b.filename,
        "target_table": b.target_table,
        "status":      b.status,
        "row_count":   b.row_count,
        "error_count": b.error_count,
        "errors":      json.loads(b.errors_json)[:20] if b.errors_json else [],
        "error_message": b.error_message,
        "run_by":      b.run_by,
        "started_at":  _fmt_dt(b.started_at),
        "completed_at": _fmt_dt(b.completed_at),
    }


def _alloc_batch_dict(b: BatchRun) -> dict:
    return {
        "batch_id":         b.id,
        "rule_id":          b.rule_id,
        "as_of_date":       b.as_of_date.isoformat() if b.as_of_date else None,
        "status":           b.status,
        "source_row_count": b.source_row_count,
        "output_row_count": b.output_row_count,
        "orphan_count":     b.orphan_count,
        "source_total":     b.source_total,
        "output_total":     b.output_total,
        "run_by":           b.run_by,
        "error_message":    b.error_message,
        "started_at":       _fmt_dt(b.started_at),
        "completed_at":     _fmt_dt(b.completed_at),
    }


def _ftp_run_dict(r: FtpRun) -> dict:
    return {
        "run_id":                r.id,
        "as_of_date":            r.as_of_date.isoformat() if r.as_of_date else None,
        "status":                r.status,
        "instruments_processed": r.instruments_processed,
        "instruments_matched":   r.instruments_matched,
        "instruments_skipped":   r.instruments_skipped,
        "run_by":                r.run_by,
        "error_message":         r.error_message,
        "started_at":            _fmt_dt(r.started_at),
        "completed_at":          _fmt_dt(r.completed_at),
    }


def _parse_date(val: str | None) -> date:
    if not val:
        return date.today()
    return datetime.strptime(val, "%Y-%m-%d").date()


# ── Data file routes ──────────────────────────────────────────────────────────

@bp.get("/datafile/formats")
@api_login_required
def list_formats(api_user):
    """List all available import format definitions."""
    formats = [
        {
            "format_id":    f["format_id"],
            "name":         f.get("name", ""),
            "description":  f.get("description", ""),
            "type":         f.get("type", ""),
            "target_table": f.get("target_table", ""),
        }
        for f in DATAFILE_CONFIG.get("formats", [])
    ]
    return jsonify({"formats": formats})


@bp.get("/datafile/exports")
@api_login_required
def list_exports(api_user):
    """List all available export configurations."""
    exports = [
        {
            "export_id":    e["export_id"],
            "name":         e.get("name", ""),
            "description":  e.get("description", ""),
            "format":       e.get("format", ""),
            "source_table": e.get("source_table", ""),
        }
        for e in DATAFILE_CONFIG.get("exports", [])
    ]
    return jsonify({"exports": exports})


@bp.post("/datafile/import")
@api_login_required
def api_import(api_user):
    """Trigger a data file import.

    Request body (JSON):
        format_id  — required, must match a rule in app/config/datafile/
        filename   — required, file must exist in the inbox folder
    """
    body = request.get_json(silent=True) or {}
    format_id = str(body.get("format_id", "")).strip()
    filename  = str(body.get("filename",  "")).strip()

    if not format_id:
        return jsonify({"error": "format_id is required"}), 400
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        return jsonify({"error": "filename is invalid or missing"}), 400

    try:
        batch = import_file(format_id, filename, api_user.username)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    code = 200 if batch.status == "COMPLETED" else 422
    return jsonify(_datafile_batch_dict(batch)), code


@bp.post("/datafile/export")
@api_login_required
def api_export(api_user):
    """Trigger a data file export.

    Request body (JSON):
        export_id   — required, must match a rule in app/config/datafile/
        as_of_date  — optional YYYY-MM-DD, defaults to today
    """
    body = request.get_json(silent=True) or {}
    export_id   = str(body.get("export_id",  "")).strip()
    as_of_date  = str(body.get("as_of_date", "")).strip() or None

    if not export_id:
        return jsonify({"error": "export_id is required"}), 400

    try:
        batch = export_data(export_id, api_user.username, as_of_date)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    code = 200 if batch.status == "COMPLETED" else 422
    return jsonify(_datafile_batch_dict(batch)), code


@bp.get("/datafile/batch/<batch_id>")
@api_login_required
def api_datafile_batch_status(api_user, batch_id):
    """Get status and row-level errors for a datafile batch."""
    batch = DataFileBatch.query.get(batch_id)
    if batch is None:
        return jsonify({"error": "batch not found"}), 404
    return jsonify(_datafile_batch_dict(batch))


# ── Allocation batch routes ───────────────────────────────────────────────────

@bp.get("/batch/rules")
@api_login_required
def list_rules(api_user):
    """List all active allocation rules."""
    rules = AllocationRule.query.filter_by(is_active=True).all()
    return jsonify({
        "rules": [
            {"rule_id": r.id, "name": r.name, "description": r.description,
             "source_table": r.source_table, "lookup_table": r.lookup_table,
             "output_table": r.output_table}
            for r in rules
        ]
    })


@bp.post("/batch/allocation")
@api_login_required
def api_run_allocation(api_user):
    """Run an allocation batch.

    Request body (JSON):
        rule_id    — required integer
        as_of_date — optional YYYY-MM-DD, defaults to today
    """
    body = request.get_json(silent=True) or {}
    rule_id_raw = body.get("rule_id")
    as_of_str   = str(body.get("as_of_date", "")).strip() or None

    if rule_id_raw is None:
        return jsonify({"error": "rule_id is required"}), 400
    try:
        rule_id = int(rule_id_raw)
    except (TypeError, ValueError):
        return jsonify({"error": "rule_id must be an integer"}), 400

    rule = AllocationRule.query.get(rule_id)
    if rule is None or not rule.is_active:
        return jsonify({"error": f"rule_id {rule_id} not found or inactive"}), 404

    try:
        as_of = _parse_date(as_of_str)
    except ValueError:
        return jsonify({"error": "as_of_date must be YYYY-MM-DD"}), 400

    batch = run_allocation(rule_id, as_of, api_user.username)
    code = 200 if batch.status == "COMPLETED" else 422
    return jsonify(_alloc_batch_dict(batch)), code


@bp.get("/batch/allocation/<batch_id>")
@api_login_required
def api_allocation_status(api_user, batch_id):
    """Get status of an allocation batch run."""
    batch = BatchRun.query.get(batch_id)
    if batch is None:
        return jsonify({"error": "batch not found"}), 404
    return jsonify(_alloc_batch_dict(batch))


# ── FTP batch routes ──────────────────────────────────────────────────────────

@bp.post("/batch/ftp")
@api_login_required
def api_run_ftp(api_user):
    """Run the FTP (Funds Transfer Pricing) engine.

    Request body (JSON):
        as_of_date — optional YYYY-MM-DD, defaults to today
    """
    body = request.get_json(silent=True) or {}
    as_of_str = str(body.get("as_of_date", "")).strip() or None

    try:
        as_of = _parse_date(as_of_str)
    except ValueError:
        return jsonify({"error": "as_of_date must be YYYY-MM-DD"}), 400

    ftp_run = run_ftp(as_of, api_user.username)
    code = 200 if ftp_run.status == "COMPLETED" else 422
    return jsonify(_ftp_run_dict(ftp_run)), code


@bp.get("/batch/ftp/<run_id>")
@api_login_required
def api_ftp_status(api_user, run_id):
    """Get status of an FTP run."""
    ftp_run = FtpRun.query.get(run_id)
    if ftp_run is None:
        return jsonify({"error": "run not found"}), 404
    return jsonify(_ftp_run_dict(ftp_run))


# ── Multi-task batch definition & execution routes ────────────────────────────

def _task_dict(t: "BatchTask") -> dict:  # type: ignore[name-defined]
    return {
        "step_order": t.step_order,
        "task_type":  t.task_type,
        "ref_id":     t.ref_id,
        "label":      t.label,
    }


def _definition_dict(d: BatchDefinition, include_steps: bool = False) -> dict:
    result = {
        "definition_id":    d.id,
        "name":             d.name,
        "description":      d.description,
        "continue_on_error": d.continue_on_error,
        "is_active":        d.is_active,
        "step_count":       len(d.tasks),
        "created_by":       d.created_by,
        "created_at":       _fmt_dt(d.created_at),
    }
    if include_steps:
        result["steps"] = [_task_dict(t) for t in d.tasks]
    return result


def _exec_step_dict(s: BatchExecutionStep) -> dict:
    return {
        "step_order":    s.step_order,
        "task_type":     s.task_type,
        "ref_id":        s.ref_id,
        "label":         s.label,
        "status":        s.status,
        "ref_run_id":    s.ref_run_id,
        "summary":       s.summary,
        "error_message": s.error_message,
        "started_at":    _fmt_dt(s.started_at),
        "completed_at":  _fmt_dt(s.completed_at),
    }


def _execution_dict(e: BatchExecution, include_steps: bool = True) -> dict:
    result = {
        "execution_id":   e.id,
        "definition_id":  e.definition_id,
        "definition_name": e.definition.name if e.definition else None,
        "as_of_date":     e.as_of_date.isoformat() if e.as_of_date else None,
        "status":         e.status,
        "run_by":         e.run_by,
        "error_message":  e.error_message,
        "started_at":     _fmt_dt(e.started_at),
        "completed_at":   _fmt_dt(e.completed_at),
    }
    if include_steps:
        result["steps"] = [_exec_step_dict(s) for s in e.steps]
    return result


@bp.get("/batch/definitions")
@api_login_required
def api_list_definitions(api_user):
    """List all active multi-task batch definitions."""
    defs = BatchDefinition.query.filter_by(is_active=True).order_by(BatchDefinition.name).all()
    return jsonify({"definitions": [_definition_dict(d) for d in defs]})


@bp.get("/batch/definitions/<int:def_id>")
@api_login_required
def api_get_definition(api_user, def_id):
    """Get a single batch definition including its ordered steps."""
    d = BatchDefinition.query.get(def_id)
    if d is None:
        return jsonify({"error": "definition not found"}), 404
    return jsonify(_definition_dict(d, include_steps=True))


@bp.post("/batch/definitions/<int:def_id>/run")
@api_login_required
def api_run_definition(api_user, def_id):
    """Execute a multi-task batch definition.

    Request body (JSON):
        as_of_date — optional YYYY-MM-DD, defaults to today

    All steps run sequentially. If continue_on_error=false (default), execution
    stops on the first failure and remaining steps are marked SKIPPED.

    Returns the full execution record with per-step results.
    """
    d = BatchDefinition.query.get(def_id)
    if d is None:
        return jsonify({"error": "definition not found"}), 404
    if not d.is_active:
        return jsonify({"error": "definition is inactive"}), 400

    body = request.get_json(silent=True) or {}
    as_of_str = str(body.get("as_of_date", "")).strip() or None
    try:
        as_of = _parse_date(as_of_str)
    except ValueError:
        return jsonify({"error": "as_of_date must be YYYY-MM-DD"}), 400

    execution = run_batch(def_id, as_of, api_user.username)

    failed = sum(1 for s in execution.steps if s.status == "FAILED")
    code = 200 if execution.status == "COMPLETED" else 422
    return jsonify(_execution_dict(execution)), code


@bp.get("/batch/executions/<exec_id>")
@api_login_required
def api_execution_status(api_user, exec_id):
    """Get full status and per-step results of a multi-task batch execution."""
    execution = BatchExecution.query.get(exec_id)
    if execution is None:
        return jsonify({"error": "execution not found"}), 404
    return jsonify(_execution_dict(execution))
