"""Use low/medium/high urgency and add Role 2 matching fields.

Changes:
  * ``request_urgency`` and ``ai_result_urgency`` enums: Normal/Urgent/Medical
    become low/medium/high (Normal -> low, Urgent -> high, Medical -> high).
  * ``ai_results`` gains latitude, longitude, location_source, medical_concern,
    and delivery_mode.

0001 builds tables from the current models, so a database created from 0001
after this change already has the new shape. Every step below checks first and
skips work that is already done.
"""

import sqlalchemy as sa
from alembic import op


revision = "0002_unified_urgency"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None

_NEW_COLUMNS = [
    sa.Column("latitude", sa.Float(), nullable=True),
    sa.Column("longitude", sa.Float(), nullable=True),
    sa.Column("location_source", sa.String(length=100), nullable=True),
    sa.Column("medical_concern", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("delivery_mode", sa.String(length=20), nullable=True),
]

# (table, column, enum type, default)
_URGENCY_COLUMNS = [
    ("requests", "urgency", "request_urgency", "low"),
    ("ai_results", "urgency", "ai_result_urgency", None),
]
_LEGACY_TO_NEW = {"Normal": "low", "Urgent": "high", "Medical": "high"}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing = {column["name"] for column in inspector.get_columns("ai_results")}
    for column in _NEW_COLUMNS:
        if column.name not in existing:
            op.add_column("ai_results", column.copy())

    if bind.dialect.name == "postgresql":
        for table, column, type_name, default in _URGENCY_COLUMNS:
            _convert_postgres_enum(bind, table, column, type_name, default)
    else:
        # Non-native enums (SQLite) store plain strings; just rewrite values.
        for table, column, _type_name, _default in _URGENCY_COLUMNS:
            for old, new in _LEGACY_TO_NEW.items():
                bind.execute(sa.text(f"UPDATE {table} SET {column} = :new WHERE {column} = :old"), {"new": new, "old": old})


def _convert_postgres_enum(bind, table: str, column: str, type_name: str, default: str | None) -> None:
    labels = [
        row[0]
        for row in bind.execute(
            sa.text(
                "SELECT e.enumlabel FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid "
                "WHERE t.typname = :name"
            ),
            {"name": type_name},
        )
    ]
    if set(labels) == {"low", "medium", "high"}:
        return  # already converted

    op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} DROP DEFAULT")
    op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE VARCHAR(20) USING {column}::text")
    for old, new in _LEGACY_TO_NEW.items():
        op.execute(f"UPDATE {table} SET {column} = '{new}' WHERE {column} = '{old}'")
    op.execute(f"DROP TYPE IF EXISTS {type_name}")
    op.execute(f"CREATE TYPE {type_name} AS ENUM ('low', 'medium', 'high')")
    op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE {type_name} USING {column}::{type_name}")
    if default:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT '{default}'")


def downgrade() -> None:
    raise NotImplementedError(
        "Downgrade is not supported: Urgent and Medical both became 'high', so the "
        "original values cannot be restored."
    )
