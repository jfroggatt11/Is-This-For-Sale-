"""Small shared schema. Coordinates always use WGS84 decimal degrees."""

import math
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

PROPERTY_TYPES = frozenset(
    {
        "residential",
        "land",
        "commercial",
        "agricultural",
        "industrial",
        "garage",
        "development",
        "mixed",
        "other",
    }
)
PRECISIONS = frozenset({"exact", "approximate", "area_only", "unknown"})


def coordinates(latitude: float, longitude: float) -> None:
    for value, limit, name in ((latitude, 90, "latitude"), (longitude, 180, "longitude")):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name} must be a number")
        if not math.isfinite(value) or not -limit <= value <= limit:
            raise ValueError(f"{name} must be finite and between {-limit} and {limit}")


@dataclass(frozen=True)
class SearchQuery:
    latitude: float
    longitude: float
    radius_m: float = 1000
    property_types: tuple[str, ...] | None = None
    country: str | None = None
    include_unlocated: bool = False

    def __post_init__(self) -> None:
        coordinates(self.latitude, self.longitude)
        if (
            isinstance(self.radius_m, bool)
            or not isinstance(self.radius_m, (int, float))
            or not math.isfinite(self.radius_m)
            or not 0 < self.radius_m <= 200_000
        ):
            raise ValueError("radius must be greater than 0 and at most 200000 metres")
        if self.property_types is not None:
            if isinstance(self.property_types, str) or not self.property_types:
                raise ValueError("property_types must be a nonempty sequence or None")
            if set(self.property_types) - PROPERTY_TYPES:
                raise ValueError("unknown property type")
            object.__setattr__(self, "property_types", tuple(self.property_types))
        if self.country is not None:
            if not re.fullmatch(r"[A-Za-z]{2}", self.country):
                raise ValueError("country must be a two-letter ISO code")
            object.__setattr__(self, "country", self.country.upper())


@dataclass(frozen=True)
class PublisherReference:
    """An aggregator's attribution, not independent verification of a listing."""

    publisher: str
    url: str
    observed_via: str
    verification: str = field(default="not_fetched", init=False)

    def __post_init__(self) -> None:
        p = urlsplit(self.url)
        if (
            p.scheme not in {"http", "https"}
            or not p.hostname
            or p.username
            or p.password
            or p.port
            or p.hostname.removeprefix("www.") != self.publisher
            or not self.observed_via
            or p.query
            or p.fragment
            or any(c.isspace() or ord(c) < 32 for c in self.url)
        ):
            raise ValueError("invalid publisher reference")


@dataclass(frozen=True)
class Listing:
    source: str
    source_id: str
    title: str
    url: str | None = None
    price: float | None = None
    currency: str | None = None
    property_type: str = "other"
    latitude: float | None = None
    longitude: float | None = None
    location_precision: str = "unknown"
    area_m2: float | None = None
    bedrooms: int | None = None
    address: str | None = None
    municipality: str | None = None
    description: str | None = None
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    raw: dict[str, Any] = field(default_factory=dict)
    publisher_references: tuple[PublisherReference, ...] = ()

    def __post_init__(self) -> None:
        if not all(
            isinstance(v, str) and v.strip() for v in (self.source, self.source_id, self.title)
        ):
            raise ValueError("source, source_id and title are required")
        if self.property_type not in PROPERTY_TYPES or self.location_precision not in PRECISIONS:
            raise ValueError("invalid taxonomy or location precision")
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("both coordinates must be present or absent")
        if self.latitude is not None:
            coordinates(self.latitude, self.longitude)
        elif self.location_precision in {"exact", "approximate"}:
            raise ValueError("exact/approximate precision requires coordinates")
        for value in (self.price, self.area_m2, self.bedrooms):
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0
            ):
                raise ValueError("numeric listing fields must be finite and nonnegative")
        if self.bedrooms is not None and not isinstance(self.bedrooms, int):
            raise ValueError("bedrooms must be an integer")
        if self.currency is not None and not re.fullmatch(r"[A-Z]{3}", self.currency):
            raise ValueError("currency must be a three-letter code")
        if self.url:
            parsed = urlsplit(self.url)
            if parsed.scheme not in {"https", "http"} or not parsed.hostname:
                raise ValueError("listing URL must be absolute HTTP(S)")
            if parsed.username or parsed.password:
                raise ValueError("listing URL must not contain credentials")
        if self.retrieved_at.tzinfo is None or self.retrieved_at.utcoffset() is None:
            raise ValueError("retrieved_at must be timezone-aware")
        if any(not isinstance(ref, PublisherReference) for ref in self.publisher_references):
            raise ValueError("publisher_references must contain PublisherReference values")
        object.__setattr__(self, "publisher_references", tuple(self.publisher_references))

    def to_dict(self) -> dict:
        result = asdict(self)
        result["retrieved_at"] = self.retrieved_at.isoformat()
        return result


@dataclass
class SearchHit:
    listing: Listing
    distance_m: float | None
    radius_match: str  # within_radius, approximate, or unverified
    duplicates: list[dict[str, str | None]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            **self.listing.to_dict(),
            "distance_m": self.distance_m,
            "radius_match": self.radius_match,
            "duplicates": self.duplicates,
        }


@dataclass
class SourceOutcome:
    source: str
    status: str
    count: int = 0
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class SearchReport:
    query: SearchQuery
    country: str | None
    status: str
    results: list[SearchHit] = field(default_factory=list)
    sources: list[SourceOutcome] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    coverage: list[dict[str, str]] = field(default_factory=list)

    def publisher_coverage(self) -> list[dict]:
        """Counts refer to returned hits; publishers overlap and were not queried."""
        counts = {}
        for hit in self.results:
            refs = hit.listing.publisher_references
            for publisher in {ref.publisher for ref in refs}:
                row = counts.setdefault(publisher, {"hits": 0, "urls": set(), "via": set()})
                row["hits"] += 1
                row["urls"].update(ref.url for ref in refs if ref.publisher == publisher)
                row["via"].update(ref.observed_via for ref in refs if ref.publisher == publisher)
        return [
            {
                "publisher": publisher,
                "matched_listings": row["hits"],
                "distinct_urls": len(row["urls"]),
                "observed_via": sorted(row["via"]),
                "verification": "not_fetched",
            }
            for publisher, row in sorted(counts.items())
        ]

    def to_dict(self) -> dict:
        return {
            "coverage": {
                "exhaustive": False,
                "catalogued_sources": self.coverage,
                "publisher_references": self.publisher_coverage(),
            },
            "query": asdict(self.query),
            "country": self.country,
            "status": self.status,
            "results": [x.to_dict() for x in self.results],
            "sources": [asdict(x) for x in self.sources],
            "warnings": self.warnings,
        }
