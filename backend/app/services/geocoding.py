"""Geocoding: turn the free-text location from an SMS into coordinates.

The matcher ranks resources by distance, so it needs latitude/longitude. Bedrock
only extracts the location *text* ("near Tully Road"); it never produces
coordinates. This module fills that gap.

Providers (``GEOCODING_PROVIDER`` setting):
  * ``gazetteer`` (default) - offline lookup of a few SIMULATED demo landmarks
    in San Jose. Works with no AWS access; every result is labeled simulated.
  * ``aws_location`` - Amazon Location Service (``geo-places`` Geocode API),
    biased toward San Jose. If the call fails or the match score is low, it
    falls back to the gazetteer instead of failing the request.

A location that cannot be resolved returns ``None``. Callers must then ask the
person for a cross street rather than guess.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app.core.config import settings

logger = logging.getLogger(__name__)

GAZETTEER_SOURCE = "demo_gazetteer (simulated)"
AWS_LOCATION_SOURCE = "aws_location_service"
MIN_AWS_MATCH_SCORE = 0.5


@dataclass(frozen=True)
class GeocodeResult:
    latitude: float
    longitude: float
    label: str
    source: str
    confidence: float


# SIMULATED demo landmarks (same points the frontend demo uses). More specific
# patterns (intersections) come first so they win over a single street name.
_GAZETTEER: list[tuple[re.Pattern[str], str, float, float]] = [
    (re.compile(r"story.*king|king.*story", re.I), "Story Rd & King Rd", 37.3492, -121.8461),
    (re.compile(r"alum rock.*white|white.*alum rock", re.I), "Alum Rock Ave & White Rd", 37.3721, -121.8189),
    (re.compile(r"senter.*capitol|capitol.*senter", re.I), "Senter Rd & Capitol Expy", 37.2969, -121.8252),
    (re.compile(r"\btully\b", re.I), "Near Tully Rd", 37.3161, -121.8401),
    (re.compile(r"mc\s?laughlin", re.I), "Near McLaughlin Ave", 37.3256, -121.8558),
    (re.compile(r"eastridge", re.I), "Near Eastridge Mall", 37.3263, -121.8113),
    (re.compile(r"alum rock", re.I), "Near Alum Rock Ave", 37.3713, -121.8343),
    (re.compile(r"\bstory\b", re.I), "Near Story Rd", 37.3305, -121.8550),
    (re.compile(r"\bsenter\b", re.I), "Near Senter Rd", 37.3105, -121.8384),
]


def geocode(location_text: str | None) -> GeocodeResult | None:
    """Resolve free text to coordinates, or return None if it cannot be resolved."""
    if not location_text or not location_text.strip():
        return None

    if settings.geocoding_provider == "aws_location":
        try:
            result = _geocode_aws(location_text)
            if result is not None:
                return result
        except Exception as error:  # noqa: BLE001 - fall back rather than fail the request
            logger.warning("Amazon Location geocode failed, using gazetteer: %s", error)

    return _geocode_gazetteer(location_text)


def _geocode_gazetteer(location_text: str) -> GeocodeResult | None:
    for pattern, label, lat, lon in _GAZETTEER:
        if pattern.search(location_text):
            return GeocodeResult(lat, lon, label, GAZETTEER_SOURCE, confidence=0.6)
    return None


def _geocode_aws(location_text: str) -> GeocodeResult | None:
    import boto3

    client = boto3.client("geo-places", region_name=settings.aws_region)
    response = client.geocode(
        QueryText=location_text,
        MaxResults=1,
        BiasPosition=[settings.geocoding_bias_longitude, settings.geocoding_bias_latitude],
        Filter={"IncludeCountries": ["USA"]},
    )
    items = response.get("ResultItems") or []
    if not items:
        return None

    item = items[0]
    score = float((item.get("MatchScores") or {}).get("Overall", 0.0))
    position = item.get("Position")  # [longitude, latitude]
    if not position or score < MIN_AWS_MATCH_SCORE:
        return None

    return GeocodeResult(
        latitude=float(position[1]),
        longitude=float(position[0]),
        label=item.get("Title") or location_text,
        source=AWS_LOCATION_SOURCE,
        confidence=score,
    )
