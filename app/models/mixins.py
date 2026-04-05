"""Reusable SQLAlchemy column mixins for common model patterns.

Usage::

    from app.models.mixins import TimestampMixin, MakerCheckerMixin

    class AllocationRule(TimestampMixin, db.Model):
        __tablename__ = "allocation_rule"
        ...

    class RefStaticAllocation(MakerCheckerMixin, db.Model):
        __tablename__ = "ref_static_allocation"
        ...  # status, maker_id, checker_id, created_at, updated_at come from mixin
"""

from app.models import db
from app.core.time_utils import utc_now


class TimestampMixin:
    """Adds ``created_at`` and ``updated_at`` audit columns."""

    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)


class MakerCheckerMixin(TimestampMixin):
    """Extends ``TimestampMixin`` with maker/checker workflow columns.

    Provides ``status``, ``maker_id``, ``checker_id``, ``created_at``,
    and ``updated_at``.  Model-specific comment columns (``comments``,
    ``maker_comment``, ``checker_comment``) are not included here — they
    remain on each individual model as they differ across tables.
    """

    status     = db.Column(db.String(20), default="DRAFT")
    maker_id   = db.Column(db.String(50), nullable=False)
    checker_id = db.Column(db.String(50), nullable=True)
