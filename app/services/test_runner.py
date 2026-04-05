"""Test runner service — invokes pytest as a subprocess and records results.

Uses pytest-json-report to get structured per-test results.  The tests
directory is resolved relative to the project root (one level above /app/).
"""

import json
import os
import subprocess
import sys
from app.core.time_utils import utc_now

from app.models import db
from app.models.test_run import TestSuiteRun

# Path to the tests/ directory — one level above app/
_TESTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "tests"))
_REPORT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "instance", "test_results"))


def run_test_suite(triggered_by: str = "system") -> TestSuiteRun:
    """
    Execute the full test suite in a subprocess and return a populated
    TestSuiteRun record saved to the database.

    The subprocess runs:
        pytest tests/ --json-report --json-report-file=<tmp.json> -q
    """
    os.makedirs(_REPORT_DIR, exist_ok=True)

    suite_run = TestSuiteRun(triggered_by=triggered_by, status="RUNNING")
    db.session.add(suite_run)
    db.session.commit()

    report_path = os.path.join(_REPORT_DIR, f"{suite_run.id}.json")

    cmd = [
        sys.executable, "-m", "pytest",
        _TESTS_DIR,
        "--json-report",
        f"--json-report-file={report_path}",
        "-q",
        "--tb=short",
        "--no-header",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10-minute hard cap
        )
        stdout = (result.stdout or "") + (result.stderr or "")
    except subprocess.TimeoutExpired:
        suite_run.status = "ERROR"
        suite_run.stdout = "Test suite timed out after 10 minutes."
        suite_run.completed_at = utc_now()
        db.session.commit()
        return suite_run
    except Exception as exc:  # pragma: no cover
        suite_run.status = "ERROR"
        suite_run.stdout = str(exc)
        suite_run.completed_at = utc_now()
        db.session.commit()
        return suite_run

    # Parse the JSON report if it was written
    report = {}
    if os.path.exists(report_path):
        try:
            with open(report_path, encoding="utf-8") as fh:
                report = json.load(fh)
        except (json.JSONDecodeError, OSError):
            pass

    summary = report.get("summary", {})
    suite_run.total    = summary.get("total",   0)
    suite_run.passed   = summary.get("passed",  0)
    suite_run.failed   = summary.get("failed",  0)
    suite_run.error    = summary.get("error",   0)
    suite_run.skipped  = summary.get("skipped", 0)
    suite_run.duration_s = report.get("duration", 0.0)
    suite_run.results_json = json.dumps(report)
    suite_run.stdout = stdout[:65535]  # cap to avoid huge DB rows

    has_failures = (suite_run.failed + suite_run.error) > 0
    if not report and result.returncode != 0:
        suite_run.status = "ERROR"
    elif has_failures:
        suite_run.status = "FAIL"
    else:
        suite_run.status = "PASS"

    suite_run.completed_at = utc_now()
    db.session.commit()
    return suite_run


def get_run_tests(suite_run: TestSuiteRun) -> list[dict]:
    """
    Parse the persisted JSON report and return a flat list of per-test result
    dicts.  Each dict has keys: node_id, outcome, duration, message, module.
    """
    if not suite_run.results_json:
        return []
    try:
        report = json.loads(suite_run.results_json)
    except (json.JSONDecodeError, TypeError):
        return []

    tests = []
    for t in report.get("tests", []):
        node_id = t.get("nodeid", "")
        # Extract module from nodeid e.g. tests/test_auth.py::TestLogin::test_xxx
        parts = node_id.split("::")
        module = parts[0].replace("\\", "/").split("/")[-1] if parts else ""
        module = module.replace(".py", "")

        call = t.get("call", {}) or {}
        longrepr = call.get("longrepr", "") or ""
        crash = call.get("crash", {}) or {}
        message = crash.get("message", "") or longrepr[:500]

        tests.append({
            "node_id": node_id,
            "module": module,
            "test_name": "::".join(parts[1:]) if len(parts) > 1 else node_id,
            "outcome": t.get("outcome", "unknown"),
            "duration": round(t.get("duration", 0.0), 4),
            "message": message,
        })

    # Sort: failures first, then by module
    tests.sort(key=lambda x: (x["outcome"] not in ("failed", "error"), x["module"], x["test_name"]))
    return tests
