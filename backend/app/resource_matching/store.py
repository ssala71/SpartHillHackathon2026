"""Resource store — loads sourced resource records into memory.

For the demo this reads a JSON file, but every consumer goes through the
``ResourceStore`` interface, so a SQLite/Postgres-backed store can be swapped in
later without touching the matcher.

Safety note: ``verified_only()`` is the gate the matcher uses. Unverified
records are never handed out for matching, which enforces the spec rule that the
system must never surface an unverified resource.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import (
    InventoryItem,
    Location,
    OperatingHours,
    Resource,
)

_DEFAULT_DATA = Path(__file__).parent / "data" / "resources.json"


class ResourceStore:
    def __init__(self, resources: list[Resource]):
        self._resources = resources

    # --- construction ---

    @classmethod
    def from_json(cls, path: str | Path = _DEFAULT_DATA) -> "ResourceStore":
        raw = json.loads(Path(path).read_text())
        resources = [cls._parse_resource(r) for r in raw.get("resources", [])]
        return cls(resources)

    @staticmethod
    def _parse_resource(d: dict) -> Resource:
        return Resource(
            resource_id=d["resource_id"],
            name=d["name"],
            verified=bool(d["verified"]),
            verified_by=d.get("verified_by"),
            last_verified_at=d.get("last_verified_at"),
            source=d.get("source", "unknown"),
            simulated=bool(d.get("simulated", False)),
            status=d["status"],
            location=Location(**d["location"]),
            operating_hours=[OperatingHours(**h) for h in d.get("operating_hours", [])],
            inventory={
                cat: InventoryItem(**item) for cat, item in d.get("inventory", {}).items()
            },
            handles_medical=bool(d.get("handles_medical", False)),
            contact=d.get("contact", {}),
        )

    # --- access ---

    def all(self) -> list[Resource]:
        return list(self._resources)

    def verified_only(self) -> list[Resource]:
        """The ONLY list the matcher is allowed to see."""
        return [r for r in self._resources if r.verified]

    def get(self, resource_id: str) -> Resource | None:
        return next((r for r in self._resources if r.resource_id == resource_id), None)
