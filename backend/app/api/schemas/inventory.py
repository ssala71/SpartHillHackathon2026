from enum import Enum
from uuid import UUID

from pydantic import Field

from app.api.schemas.common import RecordTimestamps


class InventoryStatus(str, Enum):
    AVAILABLE = "available"
    LOW = "low"
    OUT_OF_STOCK = "out_of_stock"
    RESERVED = "reserved"


class InventoryItemCreate(RecordTimestamps):
    resource_id: UUID
    item_name: str = Field(min_length=1, max_length=200)
    quantity: int = Field(ge=0)
    unit: str = Field(min_length=1, max_length=50)
    status: InventoryStatus = InventoryStatus.AVAILABLE


class InventoryItem(InventoryItemCreate):
    pass
