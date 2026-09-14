"""Shared contract suite: every implemented adapter must join CASES below."""

from datetime import datetime
from pathlib import Path

import pytest

from itsfs.adapters.base import SourceError
from itsfs.adapters.italy.demanio import ROME, DemanioAdapter
from itsfs.adapters.italy.kyero_feed import KyeroFeedAdapter
from itsfs.models import PROPERTY_TYPES, Listing

FIXTURES = Path(__file__).parents[1] / "fixtures"
CASES = ["demanio", "kyero"]


class FixtureHTTP:
    def get(self, url):
        name = "demanio_detail.html" if "id-immobile=" in url else "demanio_search.html"
        return (FIXTURES / name).read_bytes()


@pytest.fixture(params=CASES)
def adapter(request):
    http = FixtureHTTP()
    if request.param == "demanio":
        return DemanioAdapter(http, max_pages=1, now=lambda: datetime(2026, 9, 14, tzinfo=ROME))
    return KyeroFeedAdapter("kyero_test", str(FIXTURES / "kyero.xml"), http)


def test_load_and_normalize(adapter):
    assert adapter.source_name
    assert adapter.country_codes == ["IT"]
    results = adapter.search(43.779, 11.246, 2000)
    assert results
    for listing in results:
        assert isinstance(listing, Listing)
        assert listing.source == adapter.source_name
        assert listing.source_id and listing.title
        assert listing.property_type in PROPERTY_TYPES
        assert listing.retrieved_at.utcoffset() is not None
        listing.to_dict()


@pytest.mark.parametrize(
    "args",
    [
        (91, 0, 1000),
        (0, 181, 1000),
        (float("nan"), 0, 1000),
        (True, 0, 1000),
        (0, 0, -1),
        (0, 0, 0),
        (0, 0, float("inf")),
        (0, 0, "2km"),
        (0, 0, 1000, ["spaceship"]),
        (0, 0, 1000, []),
    ],
)
def test_invalid_input_before_io(adapter, args, monkeypatch):
    monkeypatch.setattr(adapter.http, "get", lambda url: pytest.fail("must validate before I/O"))
    with pytest.raises(ValueError):
        adapter.search(*args)


def test_type_filter(adapter):
    assert all(
        x.property_type == "commercial"
        for x in adapter.search(43.779, 11.246, 2000, ["commercial"])
    )


def test_network_error(adapter, monkeypatch):
    def fail(url):
        raise SourceError("network failed")

    monkeypatch.setattr(adapter.http, "get", fail)
    if isinstance(adapter, KyeroFeedAdapter):
        adapter.location = "https://example.invalid/feed.xml"
    with pytest.raises(SourceError):
        adapter.search(43.779, 11.246, 2000)


def test_all_implementations_are_in_contract_suite():
    assert set(CASES) == {
        p.stem.replace("_feed", "")
        for p in Path("src/itsfs/adapters/italy").glob("*.py")
        if p.name != "__init__.py"
    }
