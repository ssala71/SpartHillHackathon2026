"""Allocation guard — ensures confirmed allocations can never exceed stock.

This is the self-contained, in-memory implementation for Person B's demo. It is
deliberately small and sits behind the ``Allocator`` interface so Group 1 can
substitute a transactional / database-backed allocator later without changing
the matcher or callers.

Key invariant: for any resource + category, the sum of confirmed allocations
never exceeds the ``available`` count the store reported. An over-request fails
loudly rather than silently overselling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from .store import ResourceStore


class AllocationError(Exception):
    """Raised when an allocation would exceed available stock."""


@dataclass
class Allocation:
    allocation_id: str
    resource_id: str
    category: str
    quantity: int


class Allocator(Protocol):
    """Interface Group 1 can implement with a real backing store."""

    def allocate(self, resource_id: str, category: str, quantity: int) -> Allocation: ...
    def remaining(self, resource_id: str, category: str) -> int: ...


class InMemoryAllocator:
    def __init__(self, store: ResourceStore):
        self._store = store
        # resource_id -> category -> units already committed
        self._committed: dict[str, dict[str, int]] = {}
        self._counter = 0

    def remaining(self, resource_id: str, category: str) -> int:
        res = self._store.get(resource_id)
        if res is None:
            return 0
        on_hand = res.available_for(category)
        used = self._committed.get(resource_id, {}).get(category, 0)
        return on_hand - used

    def allocate(self, resource_id: str, category: str, quantity: int) -> Allocation:
        if quantity <= 0:
            raise AllocationError("quantity must be positive")

        res = self._store.get(resource_id)
        if res is None:
            raise AllocationError(f"unknown resource {resource_id!r}")
        if not res.verified:
            raise AllocationError(f"resource {resource_id!r} is not verified")

        remaining = self.remaining(resource_id, category)
        if quantity > remaining:
            raise AllocationError(
                f"cannot allocate {quantity} {category}: only {remaining} remaining "
                f"at {resource_id}"
            )

        self._committed.setdefault(resource_id, {}).setdefault(category, 0)
        self._committed[resource_id][category] += quantity
        self._counter += 1
        return Allocation(
            allocation_id=f"alloc-{self._counter:04d}",
            resource_id=resource_id,
            category=category,
            quantity=quantity,
        )
