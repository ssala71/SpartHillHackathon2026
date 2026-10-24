from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Enum, ForeignKey, JSON, Numeric, String, Text, UniqueConstraint, event, inspect
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.api.schemas.assignments import AssignmentStatus
from app.api.schemas.common import now_pacific
from app.api.schemas.incidents import IncidentStatus
from app.api.schemas.inventory import InventoryCategory, InventoryStatus
from app.api.schemas.requests import RequestChannel, RequestStatus, RequestUrgency
from app.api.schemas.resources import ResourceStatus
from app.db.base import Base


def enum_type(enum_class, name: str) -> Enum:
    return Enum(
        enum_class,
        name=name,
        native_enum=True,
        values_callable=lambda values: [item.value for item in values],
    )


class TimestampMixin:
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_pacific, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_pacific, onupdate=now_pacific, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Resource(TimestampMixin, Base):
    __tablename__ = "resources"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    status: Mapped[ResourceStatus] = mapped_column(enum_type(ResourceStatus, "resource_status"), nullable=False, default=ResourceStatus.NEEDS_VERIFICATION)


class Incident(TimestampMixin, Base):
    __tablename__ = "incidents"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    affected_area: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[IncidentStatus] = mapped_column(enum_type(IncidentStatus, "incident_status"), nullable=False, default=IncidentStatus.DRAFT)


class InventoryItem(TimestampMixin, Base):
    __tablename__ = "inventory_items"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_inventory_quantity_nonnegative"),
        UniqueConstraint("resource_id", "item_name", "category", "variant", "package_size", "package_unit", name="uq_inventory_variant"),
    )

    resource_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("resources.id"), nullable=False)
    item_name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[InventoryCategory] = mapped_column(enum_type(InventoryCategory, "inventory_category"), nullable=False)
    variant: Mapped[str | None] = mapped_column(String(100), nullable=True)
    package_size: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    package_unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    unit: Mapped[str] = mapped_column(String(30), nullable=False)
    expiration_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[InventoryStatus] = mapped_column(enum_type(InventoryStatus, "inventory_status"), nullable=False, default=InventoryStatus.AVAILABLE)


class Request(TimestampMixin, Base):
    __tablename__ = "requests"

    incident_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("incidents.id"), nullable=True)
    person_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_phone: Mapped[str] = mapped_column(String(30), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    location_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    needs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    people_count: Mapped[int | None] = mapped_column(nullable=True)
    household_size: Mapped[int | None] = mapped_column(nullable=True)
    urgency: Mapped[RequestUrgency] = mapped_column(enum_type(RequestUrgency, "request_urgency"), nullable=False, default=RequestUrgency.NORMAL)
    channel: Mapped[RequestChannel] = mapped_column(enum_type(RequestChannel, "request_channel"), nullable=False, default=RequestChannel.FRONTEND)
    status: Mapped[RequestStatus] = mapped_column(enum_type(RequestStatus, "request_status"), nullable=False, default=RequestStatus.RECEIVED)
    status_updated_by_admin_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)


@event.listens_for(Request, "before_update")
def prevent_original_message_update(_mapper, _connection, target: Request) -> None:
    if inspect(target).attrs.message.history.has_changes():
        raise ValueError("The original request message cannot be overwritten")


class Assignment(TimestampMixin, Base):
    __tablename__ = "assignments"
    __table_args__ = (
        UniqueConstraint("request_id", name="uq_assignment_active_request"),
    )

    request_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("requests.id"), nullable=False)
    resource_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("resources.id"), nullable=False)
    coordinator_user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[AssignmentStatus] = mapped_column(enum_type(AssignmentStatus, "assignment_status"), nullable=False, default=AssignmentStatus.PENDING)


class WeeklyFoodLimit(TimestampMixin, Base):
    __tablename__ = "weekly_food_limits"
    __table_args__ = (UniqueConstraint("category", name="uq_weekly_food_limit_category"),)

    category: Mapped[InventoryCategory] = mapped_column(enum_type(InventoryCategory, "weekly_limit_category"), nullable=False)
    base_limit: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    per_person_limit: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    unit: Mapped[str] = mapped_column(String(30), nullable=False)


class FoodAllocation(TimestampMixin, Base):
    __tablename__ = "food_allocations"
    __table_args__ = (
        CheckConstraint("requested_quantity >= 0", name="ck_allocation_requested_nonnegative"),
        CheckConstraint("approved_quantity >= 0", name="ck_allocation_approved_nonnegative"),
    )

    request_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("requests.id"), nullable=False)
    inventory_item_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("inventory_items.id"), nullable=False)
    household_size: Mapped[int] = mapped_column(nullable=False)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    requested_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    calculated_limit: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    approved_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    human_override: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by_user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
