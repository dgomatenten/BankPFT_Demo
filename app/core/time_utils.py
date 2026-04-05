"""Shared datetime utility — provides a timezone-aware ``utc_now`` callable.

Usage::

    from app.core.time_utils import utc_now

    # As a call site
    batch.completed_at = utc_now()

    # As a SQLAlchemy column default
    created_at = db.Column(db.DateTime, default=utc_now)
"""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)
