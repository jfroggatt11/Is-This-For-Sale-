from pathlib import Path

import pytest

from itsfs.adapters.base import AccessDenied, SourceChanged
from itsfs.adapters.italy.risorseimmobiliari import (
    BASE,
    TYPE_MAP,
    RisorseimmobiliariAdapter,
    province_paths,
)

FIXTURES = Path(__file__).parents[1] / "fixtures"
SEARCH = BASE + "/Firenze/case_in-vendita_Firenze.html"
DETAIL = BASE + "/firenze/vendita-appartamento-firenze-101.html"


class FixtureHTTP:
    def __init__(self):
        self.calls = []

    def get(self, url):
        self.calls.append(url)
        name = "risorse_search.html" if "case_in-vendita" in url else "risorse_detail.html"
        return (FIXTURES / name).read_bytes()


def body():
    return (FIXTURES / "risorse_detail.html").read_bytes()


def test_detail_normalization():
    item = RisorseimmobiliariAdapter(None).parse_detail(body(), DETAIL)
    assert item.price == 123456.5 and item.currency == "EUR"
    assert item.area_m2 == 85 and item.bedrooms == 2
    assert item.source_id == "101" and item.location_precision == "approximate"
    assert item.description is None and item.address is None
    assert "agent" not in str(item.to_dict())


@pytest.mark.parametrize("kind,expected", TYPE_MAP.items())
def test_taxonomy(kind, expected):
    data = body().replace(b"<span>Appartamento</span>", f"<span>{kind}</span>".encode())
    assert RisorseimmobiliariAdapter(None).parse_detail(data, DETAIL).property_type == expected


def test_unknown_and_optional_fields():
    data = body().replace(b"<span>Appartamento</span>", b"<span>Unknown</span>")
    data = data.replace(b"123.456,50", b"bad").replace(b"43.779", b"999")
    adapter = RisorseimmobiliariAdapter(None)
    item = adapter.parse_detail(data, DETAIL)
    assert item.property_type == "other" and item.price is None
    assert item.location_precision == "area_only" and adapter.warnings


@pytest.mark.parametrize("value", [b"Affitto", b"Venduto", b"Scaduto"])
def test_not_a_current_sale(value):
    assert (
        RisorseimmobiliariAdapter(None).parse_detail(body().replace(b"Vendita", value), DETAIL)
        is None
    )


def test_layout_and_empty():
    with pytest.raises(SourceChanged):
        RisorseimmobiliariAdapter.parse_search(b"<html>challenge</html>", SEARCH)
    data = (FIXTURES / "risorse_search.html").read_bytes().split(b"<article")[0]
    with pytest.raises(SourceChanged):
        RisorseimmobiliariAdapter.parse_search(data, SEARCH)
    assert RisorseimmobiliariAdapter.parse_search(
        data.replace(b"1 annunci", b"0 annunci"), SEARCH
    ) == ([], None)
    with pytest.raises(SourceChanged):
        RisorseimmobiliariAdapter(None).parse_detail(b"<h1>missing</h1>", DETAIL)


def test_pagination_preserves_filters():
    data = (FIXTURES / "risorse_search.html").read_bytes()
    next_url = SEARCH.replace(".html", "_pag2.html") + "?cod_categoria=R"
    data += f'<nav class="pagination"><a href="{next_url}">2</a></nav>'.encode()
    assert RisorseimmobiliariAdapter.parse_search(data, SEARCH)[1] == next_url
    with pytest.raises(SourceChanged):
        RisorseimmobiliariAdapter.parse_search(
            data.replace(b"cod_categoria=R", b"cod_categoria=C"), SEARCH
        )


def test_budget_and_failure(monkeypatch):
    monkeypatch.setattr(
        "itsfs.adapters.italy.risorseimmobiliari.province_paths",
        lambda *a: ["/Firenze/case_in-vendita_Firenze.html"],
    )
    http = FixtureHTTP()
    adapter = RisorseimmobiliariAdapter(http)
    assert len(adapter.search(43.779, 11.246, 2000)) == 1
    assert len(http.calls) == 2

    def denied(url):
        raise AccessDenied("HTTP 429")

    http.get = denied
    with pytest.raises(AccessDenied):
        adapter.search(43.779, 11.246, 2000)


def test_province_routing():
    assert province_paths(43.779, 11.246, 2000)[0] == "/Firenze/case_in-vendita_Firenze.html"
    assert province_paths(40.85, 14.27, 2000)[0].startswith("/Napoli/")
    assert len(province_paths(45.46, 9.19, 200000)) <= 3
