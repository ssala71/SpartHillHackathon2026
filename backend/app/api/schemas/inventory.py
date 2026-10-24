from datetime import date
from enum import Enum
from uuid import UUID

from pydantic import Field

from app.api.schemas.common import RecordTimestamps


class InventoryStatus(str, Enum):
    AVAILABLE = "Available"
    LOW = "Low"
    OUT_OF_STOCK = "OutOfStock"
    RESERVED = "Reserved"


class InventoryCategory(str, Enum):
    LIQUIDS = "Liquids"
    CANNED_GOODS = "CannedGoods"
    DAIRY = "Dairy"
    REFRIGERATED = "Refrigerated"
    FROZEN = "Frozen"
    DRY_GOODS = "DryGoods"
    FRESH_PRODUCE = "FreshProduce"
    READY_TO_EAT = "ReadyToEat"
    BABY_FOOD = "BabyFood"
    OTHER = "Other"


class InventoryItemCreate(RecordTimestamps):
    resource_id: UUID
    item_name: str = Field(min_length=1, max_length=200)
    category: InventoryCategory = InventoryCategory.OTHER
    quantity: int = Field(ge=0)
    unit: str = Field(min_length=1, max_length=50)
    status: InventoryStatus = InventoryStatus.AVAILABLE
    expiration_date: date | None = None


class InventoryItem(InventoryItemCreate):
    pass
