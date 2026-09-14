from dataclasses import replace

import pytest

from itsfs.dedup import canonical_url, deduplicate
from itsfs.geo import detect_country, distance_m, italian_regions, parse_radius
from itsfs.geocoding import LocalGeocoder
from itsfs.models import Listing, SearchHit, SearchQuery


@pytest.mark.parametrize(
    "text,metres", [("1000", 1000), ("2km", 2000), (" 0.5 KM ", 500), ("20m", 20)]
)
def test_radius(text, metres):
    assert parse_radius(text) == metres


@pytest.mark.parametrize("text", ["", "nan", "inf", "2mi", "-2", "2kmjunk"])
def test_bad_radius(text):
    with pytest.raises(ValueError):
        parse_radius(text)


@pytest.mark.parametrize(
    "lat,lon,country",
    [
        (40.553, 14.218, "IT"),
        (41.90, 12.50, "IT"),
        (38.12, 13.36, "IT"),
        (39.22, 9.12, "IT"),
        (48.85, 2.35, None),
        (0, 0, None),
        (42, 9, None),  # Corsica must not become Italian through its bounding box
        (43.9367, 12.4464, None),  # San Marino enclave
        (41.9029, 12.4534, None),  # Vatican enclave
    ],
)
def test_country(lat, lon, country):
    assert detect_country(lat, lon) == country


def test_country_override_and_types():
    q = SearchQuery(0, 0, 10, ["land"], "it")
    assert q.country == "IT" and q.property_types == ("land",)
    with pytest.raises(ValueError):
        SearchQuery(0, 0, 1, country="Italy")


def test_distance():
    assert distance_m(0, 0, 0, 0) == 0
    assert distance_m(0, 0, 0, 1) == pytest.approx(111195, abs=1)
    assert distance_m(0, 179.999, 0, -179.999) < 225


def test_regions_prioritize_actual_containment():
    assert italian_regions(43.77925, 11.24626, 10000)[0] == "09"
    assert italian_regions(40.553, 14.218, 2000) == ["15"]


def test_geocoder():
    g = LocalGeocoder()
    assert g.geocode("Anacapri, Italy").latitude == 40.5517
    assert g.geocode("Firenze, FI, Italy") == g.geocode("Florence, Italy")
    assert g.geocode("Milano, Italia").name == "Milan"
    assert g.municipality("not a place") is None
    with pytest.raises(ValueError):
        g.geocode("Firenze, France")


@pytest.mark.parametrize(
    "change",
    [
        {"price": -1},
        {"price": float("nan")},
        {"price": True},
        {"latitude": 40},
        {"latitude": 100, "longitude": 2},
        {"property_type": "castle"},
        {"location_precision": "exact"},
        {"bedrooms": 1.5},
        {"url": "javascript:alert(1)"},
        {"url": "https://user:secret@example.com"},
        {"currency": "euro"},
    ],
)
def test_invalid_listing(change):
    with pytest.raises(ValueError):
        Listing("test", "1", "House", **change)


def test_dedup_preserves_provenance_and_distinct_units():
    a = Listing("a", "1", "Flat", url="https://example.invalid/flat?id=1&utm_source=x")
    b = replace(a, source="b", url="https://example.invalid/flat?id=1#top")
    c = replace(a, source_id="2", url="https://example.invalid/flat?id=2")
    result = deduplicate([SearchHit(x, None, "unverified") for x in (a, b, c)])
    assert len(result) == 2 and result[0].duplicates[0]["source"] == "b"
    assert "id=2" in canonical_url(c.url)


def test_no_coordinate_price_only_merging():
    a = Listing("a", "1", "Flat", price=100, latitude=40, longitude=10)
    b = replace(a, source="b")
    assert len(deduplicate([SearchHit(x, 0, "approximate") for x in (a, b)])) == 2
