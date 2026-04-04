"""Test runner blueprint — /tests/

Routes:
  GET  /tests/          list all past runs + trigger button
  POST /tests/run       trigger a new test run (admin only), redirect to detail
  GET  /tests/run/<id>  per-test result detail
  GET  /tests/run/<id>/log  raw stdout of the run
"""

from flask import Blueprint, render_template, redirect, url_for, flash, abort, make_response
from flask_login import login_required, current_user

from app.models import db
from app.models.test_run import TestSuiteRun
from app.services.test_runner import run_test_suite, get_run_tests

bp = Blueprint("tests", __name__)


def _admin_required():
    if not current_user.is_authenticated or not current_user.is_admin:
        abort(403)


# ── List ──────────────────────────────────────────────────────────────────────

@bp.get("/")
@login_required
def index():
    runs = (
        TestSuiteRun.query
        .order_by(TestSuiteRun.started_at.desc())
        .limit(50)
        .all()
    )
    return render_template("tests/index.html", runs=runs)


# ── Trigger a new run ─────────────────────────────────────────────────────────

@bp.post("/run")
@login_required
def trigger_run():
    _admin_required()
    suite_run = run_test_suite(triggered_by=current_user.username)
    flash(
        f"Test suite completed — {suite_run.passed} passed, "
        f"{suite_run.failed} failed, {suite_run.error} errors.",
        "success" if suite_run.status == "PASS" else "danger",
    )
    return redirect(url_for("tests.run_detail", run_id=suite_run.id))


# ── Per-run detail ────────────────────────────────────────────────────────────

@bp.get("/run/<run_id>")
@login_required
def run_detail(run_id):
    suite_run = TestSuiteRun.query.get_or_404(run_id)
    tests = get_run_tests(suite_run)
    # Group by module for template rendering
    modules: dict[str, list] = {}
    for t in tests:
        modules.setdefault(t["module"], []).append(t)
    return render_template(
        "tests/detail.html",
        run=suite_run,
        modules=modules,
        tests=tests,
    )


# ── Raw log ───────────────────────────────────────────────────────────────────

@bp.get("/run/<run_id>/log")
@login_required
def run_log(run_id):
    suite_run = TestSuiteRun.query.get_or_404(run_id)
    log = suite_run.stdout or "(no output captured)"
    response = make_response(log, 200)
    response.headers["Content-Type"] = "text/plain; charset=utf-8"
    return response
