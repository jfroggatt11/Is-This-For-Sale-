from datetime import datetime

import pytest

from itsfs.adapters.base import AccessDenied, SourceChanged, SourceError
from itsfs.adapters.italy.demanio import ROME, DemanioAdapter, italian_number, property_type

URL = "https://venditaimmobili.agenziademanio.it/AsteDemanio/sito.php/immobile?id-immobile=100"


@pytest.fixture
def adapter():
    return DemanioAdapter(None, now=lambda: datetime(2026, 9, 14, tzinfo=ROME))


def test_detail(adapter, fixture_bytes):
    x = adapter.parse_detail(fixture_bytes("demanio_detail.html"), URL)
    assert x.price == 195000.5 and x.area_m2 == 2142
    assert x.property_type == "commercial" and x.currency == "EUR"
    assert x.bedrooms is None and x.description is None
    assert x.address == "Via Esempio 1"
    assert x.location_precision == "area_only" and x.latitude == 43.77925
    assert x.raw["price_kind"] == "auction_starting_price"


@pytest.mark.parametrize(
    "old,new",
    [
        (b"28/09/2026 ore 12:00", b"01/09/2026 ore 12:00"),
        (b"28/09/2026 ore 12:00", b""),
        (b"28/09/2026 ore 12:00", b"sometime"),
        (b"Aggiudicazione:</th><td></td>", b"Aggiudicazione:</th><td>100</td>"),
    ],
)
def test_no_expired_awarded_or_unverified_sales(adapter, fixture_bytes, old, new):
    assert adapter.parse_detail(fixture_bytes("demanio_detail.html").replace(old, new), URL) is None


def test_deadline_exact_time(adapter, fixture_bytes):
    adapter.now = lambda: datetime(2026, 9, 28, 12, 0, tzinfo=ROME)
    assert adapter.parse_detail(fixture_bytes("demanio_detail.html"), URL) is None


def test_missing_optional_fields(adapter, fixture_bytes):
    body = fixture_bytes("demanio_detail.html").replace(b"195.000,50", b"")
    body = body.replace(b"FIRENZE", b"UNKNOWN MUNICIPALITY")
    x = adapter.parse_detail(body, URL)
    assert x.price is None and x.latitude is None and x.longitude is None


@pytest.mark.parametrize("body", [b"<html>challenge</html>", b"{}", b"<form id='ricerca'></form>"])
def test_layout_change(adapter, body):
    with pytest.raises(SourceChanged):
        adapter.parse_search(body)
    with pytest.raises(SourceChanged):
        adapter.parse_detail(body, URL)


@pytest.mark.parametrize(
    "kind,use,expected",
    [
        ("Fabbricati", "Residenziale", "residential"),
        ("Terreni", "", "land"),
        ("Terreni", "Agricola", "agricultural"),
        ("Fabbricati", "Uffici", "commercial"),
        ("Fabbricati", "Mista", "mixed"),
        ("Unknown", "Unknown", "other"),
    ],
)
def test_types(kind, use, expected):
    assert property_type(kind, use) == expected


@pytest.mark.parametrize("value", ["nan", "inf", "-5", "ask", "12,3.4", "12.3"])
def test_bad_number(value):
    with pytest.raises(ValueError):
        italian_number(value)


def test_empty_page(adapter):
    assert adapter.parse_search(
        b'<form id="ricerca"></form><span class="conteggio">Immobili 0</span>'
    ) == ([], 0)


def test_foreign_detail_link_rejected(adapter, fixture_bytes):
    body = fixture_bytes("demanio_search.html").replace(
        b"/AsteDemanio/sito.php/immobile", b"https://evil.invalid/AsteDemanio/sito.php/immobile"
    )
    with pytest.raises(SourceChanged):
        adapter.parse_search(body)


def test_pagination_preserves_filters_and_deduplicates(adapter, fixture_bytes, monkeypatch):
    monkeypatch.setattr("itsfs.adapters.italy.demanio.italian_regions", lambda *a: ["09"])
    calls = []

    class HTTP:
        def get(self, url):
            calls.append(url)
            if "id-immobile=" in url:
                return fixture_bytes("demanio_detail.html")
            page = fixture_bytes("demanio_search.html")
            return page.replace(b"=100", b"=101") if "f_np=2" in url else page

    adapter.http = HTTP()
    result = adapter.search(43.779, 11.246, 2000)
    assert [x.source_id for x in result] == ["100", "101"]
    assert len(calls) == 4
    assert all("f_regione=09" in u and "f_aggiudicati=-1" in u for u in calls if "ricerca" in u)


@pytest.mark.parametrize("failure", [SourceChanged("changed"), SourceError("timeout")])
def test_detail_failure_is_visible(adapter, fixture_bytes, monkeypatch, failure):
    monkeypatch.setattr("itsfs.adapters.italy.demanio.italian_regions", lambda *a: ["09"])

    class HTTP:
        def get(self, url):
            if "id-immobile=" in url:
                raise failure
            return fixture_bytes("demanio_search.html")

    adapter.http = HTTP()
    assert adapter.search(43.779, 11.246, 2000) == []
    assert str(failure) in adapter.warnings
    assert any("repeated" in w for w in adapter.warnings)


def test_access_denial_stops_source(adapter, fixture_bytes, monkeypatch):
    monkeypatch.setattr("itsfs.adapters.italy.demanio.italian_regions", lambda *a: ["09"])

    class HTTP:
        def get(self, url):
            if "id-immobile=" in url:
                raise AccessDenied("HTTP 429")
            return fixture_bytes("demanio_search.html")

    adapter.http = HTTP()
    with pytest.raises(AccessDenied):
        adapter.search(43.779, 11.246, 2000)


def test_optional_numeric_change_does_not_drop_listing(adapter, fixture_bytes):
    body = fixture_bytes("demanio_detail.html").replace(b"2142 (sup. catastale)", b"circa mille")
    listing = adapter.parse_detail(body, URL)
    assert listing.area_m2 is None and listing.price == 195000.5
    assert "retained as null" in adapter.warnings[0]


def test_detail_and_page_caps_are_visible(adapter, fixture_bytes, monkeypatch):
    monkeypatch.setattr("itsfs.adapters.italy.demanio.italian_regions", lambda *args: ["09"])
    calls = []

    class HTTP:
        def get(self, url):
            calls.append(url)
            if "id-immobile=" in url:
                return fixture_bytes("demanio_detail.html")
            body = fixture_bytes("demanio_search.html")
            return body + b'<a href="/AsteDemanio/sito.php/immobile?id-immobile=101">Second</a>'

    adapter.http = HTTP()
    adapter.max_details = 1
    assert len(adapter.search(43.779, 11.246, 2000)) == 1
    assert len(calls) == 2 and any("detail request limit" in w for w in adapter.warnings)
    adapter.max_details = 20
    adapter.max_pages = 1
    assert len(adapter.search(43.779, 11.246, 2000)) == 2
    assert any("page limit" in w for w in adapter.warnings)
