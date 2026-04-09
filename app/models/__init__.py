from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

db = SQLAlchemy()

# Use JSONB on PostgreSQL, plain JSON on SQLite (tests)
JSONB_TYPE = JSON().with_variant(JSONB(), "postgresql")
