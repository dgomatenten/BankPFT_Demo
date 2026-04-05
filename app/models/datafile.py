from app.models import db
from app.core.time_utils import utc_now


class DataFileBatch(db.Model):
    """Tracks each fixed-length file import or data export operation."""
    __tablename__ = "datafile_batch"

    id = db.Column(db.String(36), primary_key=True)
    operation = db.Column(db.String(10), nullable=False)        # IMPORT | EXPORT
    format_id = db.Column(db.String(50), nullable=False)        # key from datafile_config.json
    format_name = db.Column(db.String(100), nullable=True)
    filename = db.Column(db.String(255), nullable=False)
    target_table = db.Column(db.String(50), nullable=True)      # for imports
    status = db.Column(db.String(20), default="RUNNING")        # RUNNING | COMPLETED | FAILED
    row_count = db.Column(db.Integer, default=0)
    error_count = db.Column(db.Integer, default=0)
    errors_json = db.Column(db.Text, nullable=True)             # JSON list of error strings
    run_by = db.Column(db.String(50), nullable=False)
    started_at = db.Column(db.DateTime, default=utc_now)
    completed_at = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
