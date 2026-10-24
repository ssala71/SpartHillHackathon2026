"""Create the initial application schema.

This migration uses the checked-in SQLAlchemy metadata so a fresh development
RDS database can be initialized before additional hand-written migrations are
introduced.
"""

from alembic import op

from app.db import models  # noqa: F401 - registers all mapped tables
from app.db.base import Base


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
