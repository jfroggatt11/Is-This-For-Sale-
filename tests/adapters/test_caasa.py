import json
from pathlib import Path

import pytest

from itsfs.adapters.base import AccessDenied, SourceChanged
from itsfs.adapters.italy.caasa import BASE, TYPE_MAP, CaasaAdapter, sale_url

FIXTURES = Path(__file__).parents[1] / "fixtures"
SEARCH = BASE + "/firenze/firenze/appartamento/in-vendita.html?l=e"
CITY = json.loads((FIXTURES / "caasa_city.json").read_text())


class FixtureHTTP:
    def __init__(self):
        self.calls = []
        self.posts = []

    def get(self, url):
        self.calls.append(url)
        return (
            FIXTURES / ("caasa_city.json" if "/city.jsp?" in url else "caasa_search.html")
        ).read_bytes()

    def post_form(self, url, data):
        self.posts.append((url, data))
        return json.dumps({"canonical": SEARCH, "title": "Synthetic"}).encode()


def body():
    return (FIXTURES / "caasa_search.html").read_bytes()


def test_realistic_html_normalization_and_request_contract():
    http = FixtureHTTP()
    adapter = CaasaAdapter(http)
    results = adapter.search(43.779, 11.246, 2000, ["residential"])
    assert len(results) == 1
    item = results[0]
    assert item.price == 234567 and item.area_m2 == 75 and item.bedrooms is None
    assert item.location_precision == "approximate" and item.source_id == "101"
    assert item.title == "Appartamento a Firenze" and item.description is None
    assert not any("/ClickTag" in u for u in http.calls)
    url, data = http.posts[0]
    assert url == BASE + "/explain.jsp" and data["advtype"] == "S"
    request = json.loads(data["searchobject"])
    assert request["legal"] == "e"
    assert request["location"]["province"] == "FI"
    assert all(TYPE_MAP[t] == "residential" for t in request["keywords"]["homeType"])


@pytest.mark.parametrize("kind,expected", TYPE_MAP.items())
def test_type_mapping(kind, expected):
    data = body().replace(b"appartamento in vendita", (kind + " in vendita").encode())
    results, _ = CaasaAdapter(None).parse_search(data, SEARCH, CITY)
    assert results[0].property_type == expected


def test_structured_data_ignores_seller_point():
    record = {
        "@type": "WebPageElement",
        "about": {
            "identifier": "101",
            "url": "/toscana/firenze/firenze/vendita-65-opinione.html",
            "address": {"addressLocality": "Firenze"},
            "geo": {"latitude": 43.779, "longitude": 11.246},
            "floorSize": {"unitCode": "MTK", "value": 80},
        },
        "offers": {
            "name": "appartamento in vendita",
            "price": 150000,
            "priceCurrency": "EUR",
            "seller": {"geo": {"latitude": 45, "longitude": 9}, "telephone": "do not retain"},
        },
    }
    data = body().replace(
        b'<div class="result-item" id="ID_101" data-id="101">',
        b'<div class="result-item" id="ID_101" data-id="101"><script type="application/ld+json">'
        + json.dumps(record).encode()
        + b"</script>",
    )
    results, _ = CaasaAdapter(None).parse_search(data, SEARCH, CITY)
    assert results[0].latitude == 43.779 and results[0].price == 150000
    assert "telephone" not in json.dumps(results[0].to_dict())
    record["offers"]["availability"] = "https://schema.org/SoldOut"
    assert (
        CaasaAdapter(None).parse_listing(
            record, __import__("bs4").BeautifulSoup("", "html.parser"), CITY
        )
        is None
    )


def test_rental_conflict_is_not_a_sale():
    data = body().replace(b"Proponiamo in vendita", b"Proponiamo in affitto")
    adapter = CaasaAdapter(None)
    assert adapter.parse_search(data, SEARCH, CITY)[0] == []
    assert any("conflicts" in w for w in adapter.warnings)


def test_empty_vs_changed_layout():
    data = (
        body().split(b'<div class="result-item"')[0].replace(b"1 annunci", b"0 annunci")
        + b"<p>Nessun risultato trovato.</p>"
    )
    assert CaasaAdapter(None).parse_search(data, SEARCH, CITY) == ([], None)
    with pytest.raises(SourceChanged):
        CaasaAdapter(None).parse_search(b"<html>challenge</html>", SEARCH, CITY)
    with pytest.raises(SourceChanged):
        CaasaAdapter(None).parse_search(data.replace(b"0 annunci", b"9 annunci"), SEARCH, CITY)


def test_optional_bad_numbers_coordinates_and_missing_currency():
    adapter = CaasaAdapter(None)
    data = body().replace(b"234.567", b"not-price").replace(b"43.779%2C11.246", b"NaN%2C11.246")
    result = adapter.parse_search(data, SEARCH, CITY)[0][0]
    assert result.price is None and result.location_precision == "area_only"
    assert adapter.warnings


def test_city_point_not_property_point():
    data = body().replace(b"43.779%2C11.246", b"43.77%2C11.25")
    assert (
        CaasaAdapter(None).parse_search(data, SEARCH, CITY)[0][0].location_precision == "area_only"
    )


def test_pagination_dedup_repeat_and_caps():
    http = FixtureHTTP()
    original_get = http.get
    next_url = SEARCH + "&page=2"

    def pages(url):
        data = original_get(url)
        if "/city.jsp?" not in url:
            data += f'<a href="{next_url}">2</a>'.encode()
        return data

    http.get = pages
    adapter = CaasaAdapter(http)
    assert len(adapter.search(43.779, 11.246, 2000)) == 1
    assert any("repeated listings" in w for w in adapter.warnings)
    adapter = CaasaAdapter(http, max_pages=1)
    assert len(adapter.search(43.779, 11.246, 2000)) == 1
    assert any("page limit" in w for w in adapter.warnings)
    with pytest.raises(SourceChanged):
        adapter.parse_search(
            body() + f'<a href="{next_url.replace("l=e", "l=i")}">2</a>'.encode(), SEARCH, CITY
        )


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.invalid/firenze/firenze/appartamento/in-vendita.html?l=e",
        "/ClickTag?url=x",
        "/firenze/firenze/appartamento/in-vendita.html",
        "/firenze/firenze/appartamento/in-affitto.html?l=e",
    ],
)
def test_resolver_urls_restricted(url):
    with pytest.raises(SourceChanged):
        sale_url(url)


def test_denial_stops_source():
    http = FixtureHTTP()

    def denied(*a):
        raise AccessDenied("HTTP 429")

    http.post_form = denied
    with pytest.raises(AccessDenied):
        CaasaAdapter(http).search(43.779, 11.246, 2000)
    assert len(http.calls) == 1


def test_neighbour_selection_and_city_limit():
    city = {
        **CITY,
        "neighbours": [
            {
                "id": "scandicci",
                "province": "FI",
                "bounds": {"nw": {"lat": 43.8, "lng": 11.2}, "se": {"lat": 43.7, "lng": 11.3}},
            }
        ],
    }
    http = FixtureHTTP()
    get = http.get
    http.get = lambda url: json.dumps(city).encode() if "/city.jsp?" in url else get(url)
    adapter = CaasaAdapter(http, max_cities=1)
    adapter.search(43.779, 11.246, 2000)
    assert any("municipality request limit" in w for w in adapter.warnings)
