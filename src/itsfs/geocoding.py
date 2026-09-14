"""Replaceable geocoder interface; bundled Italian town lookup makes no requests."""

import json
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from typing import Protocol


def normalize(value: str) -> str:
    return " ".join(
        "".join(
            c
            for c in unicodedata.normalize("NFKD", value.casefold())
            if not unicodedata.combining(c)
        )
        .replace("-", " ")
        .split()
    )


@dataclass(frozen=True)
class Place:
    name: str
    latitude: float
    longitude: float
    country: str = "IT"
    precision: str = "area_only"


class Geocoder(Protocol):
    def geocode(self, location: str) -> Place: ...


@lru_cache(maxsize=1)
def towns() -> list[dict]:
    return json.loads(files("itsfs").joinpath("data/towns.json").read_text())


class LocalGeocoder:
    def geocode(self, location: str) -> Place:
        parts = [normalize(p) for p in location.split(",")]
        if len(parts) > 1 and parts[-1] in {"italy", "italia", "it"}:
            parts.pop()
        if not 1 <= len(parts) <= 2 or not all(parts):
            raise ValueError("use Town[, Province code][, Italy] or explicit --lat/--lon")
        matches = [
            t
            for t in towns()
            if parts[0] in t["names"] and (len(parts) == 1 or parts[1] == normalize(t["province"]))
        ]
        # Identical alternative spellings can occur in neighboring populated places.
        if len(matches) != 1:
            reason = "ambiguous" if matches else "not found in the bundled Italian gazetteer"
            raise ValueError(f"location {reason}; add a province code or use --lat/--lon")
        t = matches[0]
        return Place(t["name"], t["lat"], t["lon"])

    def municipality(self, name: str, province: str | None = None) -> Place | None:
        try:
            return self.geocode(f"{name}, {province}, Italy" if province else f"{name}, Italy")
        except ValueError:
            return None
