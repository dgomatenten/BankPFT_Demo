"""Dashboard alert engine.

Each check returns a list of AlertItem objects describing anything that
requires operator attention.  All checks are read-only and safe to run on
every dashboard page load.

Severity levels:
  danger  — something is broken or blocked (failed runs, failed uploads)
  warning — action required soon (pending approvals, stale dates)
  info    — informational attention (files waiting in inbox)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Literal

SeverityT = Literal["danger", "warning", "info"]

_SEVERITY_ORDER = {"danger": 0, "warning": 1, "info": 2}


@dataclass
class AlertItem:
    severity: SeverityT
    icon: str
    message: str
    link: str | None = field(default=None)


def get_dashboard_alerts() -> list[AlertItem]:
    """Return all active alert items sorted by severity (danger first)."""
    alerts: list[AlertItem] = []
    alerts.extend(_check_failed_uploads())
    alerts.extend(_check_failed_batches())
    alerts.extend(_check_pending_uploads())
    alerts.extend(_check_inbox_files())
    alerts.extend(_check_stale_processing_date())
    alerts.extend(_check_configured_alerts())
    return sorted(alerts, key=lambda a: _SEVERITY_ORDER[a.severity])


# ── Individual checks ────────────────────────────────────────────────────────

def _check_failed_uploads() -> list[AlertItem]:
    """Upload batches that failed validation in the last 7 days."""
    try:
        from app.models.workflow import UploadBatch
        cutoff = datetime.utcnow() - timedelta(days=7)
        count = UploadBatch.query.filter(
            UploadBatch.status == "FAILED",
            UploadBatch.created_at >= cutoff,
        ).count()
        if count == 0:
            return []
        noun = "batch" if count == 1 else "batches"
        return [AlertItem(
            severity="danger",
            icon="bi-exclamation-triangle-fill",
            message=f"{count} upload {noun} failed validation in the last 7 days.",
            link="/upload",
        )]
    except Exception:
        return []


def _check_failed_batches() -> list[AlertItem]:
    """Batch executions that failed or partially completed in the last 7 days."""
    try:
        from app.models.workflow import BatchExecution
        cutoff = datetime.utcnow() - timedelta(days=7)
        count = BatchExecution.query.filter(
            BatchExecution.status.in_(["FAILED", "PARTIAL"]),
            BatchExecution.started_at >= cutoff,
        ).count()
        if count == 0:
            return []
        noun = "execution" if count == 1 else "executions"
        return [AlertItem(
            severity="danger",
            icon="bi-x-circle-fill",
            message=f"{count} batch {noun} failed or completed partially in the last 7 days.",
            link="/batch",
        )]
    except Exception:
        return []


def _check_pending_uploads() -> list[AlertItem]:
    """Upload batches awaiting checker approval."""
    try:
        from app.models.workflow import UploadBatch
        count = UploadBatch.query.filter_by(status="PENDING").count()
        if count == 0:
            return []
        noun = "batch" if count == 1 else "batches"
        return [AlertItem(
            severity="warning",
            icon="bi-hourglass-split",
            message=f"{count} upload {noun} pending checker approval.",
            link="/upload",
        )]
    except Exception:
        return []


def _check_inbox_files() -> list[AlertItem]:
    """Files sitting in the data file inbox that have not yet been imported."""
    try:
        from app.services.datafile_service import list_inbox_files
        files = list_inbox_files()
        count = len(files)
        if count == 0:
            return []
        noun = "file" if count == 1 else "files"
        names = ", ".join(f["filename"] for f in files[:3])
        suffix = f" … (+{count - 3} more)" if count > 3 else ""
        return [AlertItem(
            severity="info",
            icon="bi-inbox",
            message=f"{count} {noun} waiting in data file inbox: {names}{suffix}",
            link="/datafile",
        )]
    except Exception:
        return []


def _check_stale_processing_date() -> list[AlertItem]:
    """Processing date operation variable is unset or more than 3 days behind today."""
    try:
        from app.models.workflow import OperationVariable
        var = OperationVariable.query.filter_by(key="processing_date", is_active=True).first()
        if not var or not var.value:
            return [AlertItem(
                severity="warning",
                icon="bi-calendar-x",
                message="Processing date is not set. Set it in Operation Variables before running batches.",
                link="/admin/op-vars",
            )]
        proc_date = datetime.strptime(var.value, "%Y-%m-%d").date()
        delta = (date.today() - proc_date).days
        if delta > 3:
            return [AlertItem(
                severity="warning",
                icon="bi-calendar-x",
                message=(
                    f"Processing date ({var.value}) is {delta} day{'s' if delta != 1 else ''} "
                    "behind today. Update it in Operation Variables."
                ),
                link="/admin/op-vars",
            )]
    except Exception:
        pass
    return []


def _check_configured_alerts() -> list[AlertItem]:
    """Evaluate all active AlertConfig rules against the current processing_date."""
    results: list[AlertItem] = []
    try:
        from app.models.workflow import AlertConfig, OperationVariable
        from app.models.registry import MODEL_REGISTRY

        # Resolve processing_date once
        proc_date: date | None = None
        var = OperationVariable.query.filter_by(key="processing_date", is_active=True).first()
        if var and var.value:
            try:
                proc_date = datetime.strptime(var.value, "%Y-%m-%d").date()
            except ValueError:
                pass

        configs = AlertConfig.query.filter_by(is_active=True).order_by(AlertConfig.name).all()
        for cfg in configs:
            try:
                if cfg.check_type == "table_row_check":
                    results.extend(_run_table_row_check(cfg, proc_date, MODEL_REGISTRY))
            except Exception:
                # Silently skip broken configs so the dashboard always loads
                pass
    except Exception:
        pass
    return results


def _run_table_row_check(
    cfg,
    proc_date: "date | None",
    model_registry: dict,
) -> list[AlertItem]:
    """Return an AlertItem if the table has no rows for proc_date on cfg.date_column."""
    if not cfg.table_name or not cfg.date_column:
        return []

    model = model_registry.get(cfg.table_name)
    if model is None:
        return []

    if proc_date is None:
        # Can't check without a processing date — skip silently
        return []

    col = getattr(model, cfg.date_column, None)
    if col is None:
        return []

    count = model.query.filter(col == proc_date).count()
    if count > 0:
        return []  # data exists — no alert

    icon_map = {"danger": "bi-exclamation-triangle-fill",
                "warning": "bi-exclamation-circle",
                "info": "bi-info-circle"}
    return [AlertItem(
        severity=cfg.severity,
        icon=icon_map.get(cfg.severity, "bi-exclamation-circle"),
        message=f"{cfg.name}: no data found in '{cfg.table_name}' for processing date {proc_date}.",
        link="/admin/alert-configs",
    )]
