import pytest
from sqlalchemy import CheckConstraint

from app.db.base import Base
from app.db.models import InventoryItem
from app.db.session import create_database_engine


def test_all_storage_tables_are_registered() -> None:
    expected = {
        "resources",
        "incidents",
        "inventory_items",
        "requests",
        "assignments",
        "weekly_food_limits",
        "food_allocations",
    }

    assert expected.issubset(Base.metadata.tables)


def test_inventory_quantity_is_nonnegative() -> None:
    constraints = InventoryItem.__table__.constraints

    assert any(
        isinstance(constraint, CheckConstraint)
        and constraint.name == "ck_inventory_quantity_nonnegative"
        for constraint in constraints
    )


def test_database_connection_requires_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.db.session.settings.database_url", None)

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        create_database_engine()
