import pytest

from itsfs.adapters.base import SourceChanged
from itsfs.adapters.italy.kyero_feed import TYPE_MAP, KyeroFeedAdapter


@pytest.fixture
def adapter():
    return KyeroFeedAdapter("test", "unused", None)


def test_normalization_and_missing_fields(adapter, fixture_bytes):
    results = adapter.parse(fixture_bytes("kyero.xml"))
    assert len(results) == 4  # excludes rent, Spain and missing country
    home, land, shop, other = results
    assert home.price == 195000 and home.bedrooms == 3 and home.area_m2 == 120
    assert home.description == "Annuncio di prova."
    assert land.area_m2 == 2000 and land.bedrooms is None
    assert shop.price is None and shop.url is None
    assert other.latitude is None and other.property_type == "other"


@pytest.mark.parametrize(
    "body",
    [
        b"<html>challenge</html>",
        b"<root>",
        b"<root><kyero><feed_version>4</feed_version></kyero></root>",
        b'<!DOCTYPE x [<!ENTITY x "hi">]><root>&x;</root>',
        b"<root><kyero><feed_version>3</feed_version></kyero><listing/></root>",
    ],
)
def test_changed_or_unsafe_format(adapter, body):
    with pytest.raises(SourceChanged):
        adapter.parse(body)


def test_empty_snapshot(adapter):
    assert adapter.parse(b"<root><kyero><feed_version>3</feed_version></kyero></root>") == []


@pytest.mark.parametrize("value", [b"nan", b"-1", b"infinity", b"bad"])
def test_bad_optional_number_skips_record_visibly(adapter, fixture_bytes, value):
    results = adapter.parse(fixture_bytes("kyero.xml").replace(b"195000", value))
    assert len(results) == 3 and adapter.warnings


def test_category_coverage():
    assert {
        "residential",
        "land",
        "commercial",
        "agricultural",
        "industrial",
        "garage",
        "development",
        "mixed",
    } <= set(TYPE_MAP.values())


@pytest.mark.parametrize("upstream,expected", list(TYPE_MAP.items()))
def test_every_category_mapping_through_parser(adapter, fixture_bytes, upstream, expected):
    body = fixture_bytes("kyero.xml").replace(
        b"<type>villa</type>", f"<type>{upstream}</type>".encode()
    )
    assert adapter.parse(body)[0].property_type == expected
