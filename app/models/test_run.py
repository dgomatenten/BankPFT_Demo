"""TestSuiteRun model — persists each in-app pytest invocation and its results."""

from app.models import db
from datetime import datetime
import uuid


class TestSuiteRun(db.Model):
    """One row per test-suite execution triggered from the UI or API."""
    __tablename__ = "test_suite_run"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    triggered_by = db.Column(db.String(50), nullable=True)

    # Overall result
    status = db.Column(db.String(10), default="RUNNING")  # RUNNING PASS FAIL ERROR
    total = db.Column(db.Integer, default=0)
    passed = db.Column(db.Integer, default=0)
    failed = db.Column(db.Integer, default=0)
    error = db.Column(db.Integer, default=0)
    skipped = db.Column(db.Integer, default=0)
    duration_s = db.Column(db.Float, default=0.0)

    # Full pytest-json-report payload and captured stdout
    results_json = db.Column(db.Text, nullable=True)   # JSON string
    stdout = db.Column(db.Text, nullable=True)          # combined output

    def summary_dict(self):
        return {
            "id": self.id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "triggered_by": self.triggered_by,
            "status": self.status,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "error": self.error,
            "skipped": self.skipped,
            "duration_s": self.duration_s,
        }
