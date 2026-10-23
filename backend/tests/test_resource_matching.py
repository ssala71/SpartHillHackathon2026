"""Tests for Person B — matching, no-match, and allocation safety.

Run from the person_b/ directory:  python -m pytest  (or  python -m unittest)
These tests use a fixed `when` (a Monday midday) so operating-hours logic is
deterministic regardless of when the suite runs.
"""

import unittest
from datetime import datetime, timezone

from app.resource_matching.allocation import AllocationError, InMemoryAllocator
from app.resource_matching.matcher import Matcher
from app.resource_matching.models import (
    ExtractedLocation,
    ExtractionResult,
    Need,
)
from app.resource_matching.store import ResourceStore

# A Monday at 12:00 UTC — inside every demo resource's operating hours.
MONDAY_NOON = datetime(2026, 10, 19, 12, 0, 0, tzinfo=timezone.utc)

# Near Riverside (res-0001) and Eastside (res-0003, unverified).
NEAR_RIVERSIDE = ExtractedLocation(lat=34.0752, lon=-117.3698, confidence=0.9)


def make_extraction(categories, location=NEAR_RIVERSIDE, people=3):
    return ExtractionResult(
        needs=[Need(category=c, raw_text=c) for c in categories],
        location=location,
        people_count=people,
    )


class MatchingTests(unittest.TestCase):
    def setUp(self):
        self.store = ResourceStore.from_json()
        self.matcher = Matcher(self.store)

    def test_matched_picks_nearest_verified_in_stock(self):
        """A normal water request matches a verified, open, in-stock resource,
        and never the unverified Eastside pantry even though it is closer/bigger."""
        result = self.matcher.match(make_extraction(["water"]), when=MONDAY_NOON)

        self.assertEqual(result.outcome, "matched")
        self.assertIsNotNone(result.match)
        # Eastside (res-0003) is unverified → must not be chosen.
        self.assertNotEqual(result.match.resource_id, "res-0003")
        self.assertEqual(result.match.resource_id, "res-0001")
        # Fields are copied from the sourced record (not invented).
        self.assertIn("water", result.match.matched_needs)
        self.assertEqual(result.match.source, "demo_seed")
        self.assertTrue(result.match.simulated)
        self.assertIsNotNone(result.match.last_verified_at)
        self.assertIn("Nearest verified", result.match.selection_reason)
        self.assertIn("not a delivery confirmation", result.disclaimer)

    def test_no_match_when_nothing_eligible(self):
        """baby_formula: only Westend has the category and it is at zero stock,
        so the result must be an explicit no_match — not a fabricated resource."""
        result = self.matcher.match(make_extraction(["baby_formula"]), when=MONDAY_NOON)

        self.assertEqual(result.outcome, "no_match")
        self.assertIsNone(result.match)
        self.assertEqual(result.no_match_reason, "no_verified_open_in_stock_resource")

    def test_no_match_when_location_missing(self):
        result = self.matcher.match(
            make_extraction(["water"], location=ExtractedLocation()),
            when=MONDAY_NOON,
        )
        self.assertEqual(result.outcome, "no_match")
        self.assertEqual(result.no_match_reason, "no_usable_location")

    def test_closed_resource_not_matched(self):
        """Southpark (res-0004) has water but is closed → never matched.
        With Riverside also stocking water, we still match Riverside, not the
        closed depot."""
        result = self.matcher.match(make_extraction(["water"]), when=MONDAY_NOON)
        self.assertEqual(result.outcome, "matched")
        self.assertNotEqual(result.match.resource_id, "res-0004")


class AllocationTests(unittest.TestCase):
    def setUp(self):
        self.store = ResourceStore.from_json()
        self.alloc = InMemoryAllocator(self.store)

    def test_allocation_reduces_remaining(self):
        before = self.alloc.remaining("res-0001", "water")
        self.alloc.allocate("res-0001", "water", 20)
        self.assertEqual(self.alloc.remaining("res-0001", "water"), before - 20)

    def test_cannot_oversell_stock(self):
        """Confirmed allocations can never exceed stock (the Group 1 rule)."""
        on_hand = self.alloc.remaining("res-0001", "water")  # 120 in demo
        self.alloc.allocate("res-0001", "water", on_hand)     # take it all
        with self.assertRaises(AllocationError):
            self.alloc.allocate("res-0001", "water", 1)       # one more → fail

    def test_cannot_allocate_from_unverified(self):
        with self.assertRaises(AllocationError):
            self.alloc.allocate("res-0003", "water", 1)       # Eastside unverified


if __name__ == "__main__":
    unittest.main()
