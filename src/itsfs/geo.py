"""Offline Italy containment; never infer a country from a bounding box alone."""

import json
import math
import re
from functools import lru_cache
from importlib.resources import files

from .models import coordinates


def parse_radius(value: str) -> float:
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(km|m)?\s*", value, re.I)
    if not match:
        raise ValueError("radius must look like 1000, 500m, or 2km")
    return float(match[1]) * (1000 if (match[2] or "").lower() == "km" else 1)


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    a = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 6_371_008.8 * 2 * math.asin(math.sqrt(min(1, max(0, a))))


def _in_ring(x: float, y: float, ring: list) -> bool:
    inside = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:], strict=False):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


@lru_cache(maxsize=1)
def _italy_polygons() -> list:
    data = json.loads(files("itsfs").joinpath("data/italy.geojson").read_text())
    polygons = []
    for feature in data["features"]:
        geo = feature["geometry"]
        polygons.extend(
            geo["coordinates"] if geo["type"] == "MultiPolygon" else [geo["coordinates"]]
        )
    return polygons


def detect_country(latitude: float, longitude: float) -> str | None:
    coordinates(latitude, longitude)
    if not (35 <= latitude <= 48 and 6 <= longitude <= 19):
        return None
    for polygon in _italy_polygons():
        if _in_ring(longitude, latitude, polygon[0]) and not any(
            _in_ring(longitude, latitude, hole) for hole in polygon[1:]
        ):
            return "IT"
    return None


def italian_regions(latitude: float, longitude: float, radius_m: float) -> list[str]:
    """Conservative box overlap; false positives are filtered later."""
    data = json.loads(files("itsfs").joinpath("data/regions.json").read_text())
    dy = radius_m / 110_000
    dx = dy / max(0.01, math.cos(math.radians(latitude + dy)))
    candidates = [
        r
        for r in data
        if r["bbox"][0] <= longitude + dx
        and r["bbox"][2] >= longitude - dx
        and r["bbox"][1] <= latitude + dy
        and r["bbox"][3] >= latitude - dy
    ]

    def contains(r):
        geo = r["geometry"]
        polygons = geo["coordinates"] if geo["type"] == "MultiPolygon" else [geo["coordinates"]]
        return any(
            _in_ring(longitude, latitude, p[0])
            and not any(_in_ring(longitude, latitude, hole) for hole in p[1:])
            for p in polygons
        )

    return [r["code"] for r in sorted(candidates, key=lambda r: not contains(r))]
