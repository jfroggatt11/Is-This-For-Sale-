"""Attribution is unverified metadata, never another fetch or identity match."""

from dataclasses import replace
from html import escape
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import pytest
from bs4 import BeautifulSoup

from itsfs.adapters.italy.caasa import BASE, CaasaAdapter, publisher_references
from itsfs.cli import main
from itsfs.dedup import deduplicate
from itsfs.models import Listing, PublisherReference, SearchHit, SearchQuery, SearchReport
from itsfs.registry import Registry

FIXTURE = Path(__file__).parent / "fixtures" / "caasa_search.html"
SEARCH = BASE + "/firenze/firenze/appartamento/in-vendita.html?l=e"


def link(url, *, sid="101", tracker="/ClickTag", agency="wrong-label"):
    return (
        '<a href="'
        + escape(
            tracker
            + "?"
            + urlencode(
                {
                    "url": url,
                    "adv": sid,
                    "agency": agency,
                }
            ),
            quote=True,
        )
        + '">publisher</a>'
    )


def page(*links):
    return FIXTURE.read_text().replace(
        '<p class="main-description">', "".join(links) + '<p class="main-description">'
    )


def test_union_of_promoted_and_regular_card_references():
    promoted = page(link("https://www.immobiliare.it/annunci/123/")).replace("ID_101", "PID_101")
    regular = page(
        link("https://www.idealista.it/immobile/456/#xtor=tracking"),
        link("https://www.wikicasa.it/annuncio/789?utm_source=caasa"),
    )
    results, _ = CaasaAdapter(None).parse_search(promoted + regular, SEARCH, {"name": "Firenze"})
    assert len(results) == 1
    refs = results[0].publisher_references
    assert [r.publisher for r in refs] == ["idealista.it", "immobiliare.it", "wikicasa.it"]
    assert all(r.observed_via == "caasa" and r.verification == "not_fetched" for r in refs)
    assert not any(urlsplit(r.url).query or urlsplit(r.url).fragment for r in refs)
    assert results[0].source == "caasa"


@pytest.mark.parametrize(
    "anchor",
    [
        link("javascript:alert(1)"),
        link("https://user:secret@www.idealista.it/immobile/1/"),
        link("https://www.idealista.it:443/immobile/1/"),
        link("https://[invalid/path"),
        link("https://www.idealista.it/immobile/1/?token=secret"),
        link("https://www.idealista.it/immobile/1/?token="),
        link("https://www.idealista.it/immobile/1/", sid="102"),
        link("https://www.idealista.it/immobile/1/", tracker="https://evil.invalid/ClickTag"),
        link("https://www.idealista.it/immobile/1/", tracker="/ClickTagOther"),
        link("https://www.idealista.it/"),
        link("https://www.idealista.it/immobile/1/\n"),
    ],
)
def test_invalid_or_unassociated_reference_omitted(anchor):
    soup = BeautifulSoup(page(anchor), "html.parser")
    assert publisher_references(soup.select(".result-item"), "101") == ()


def test_destination_not_agency_label_controls_publisher():
    soup = BeautifulSoup(
        page(link("https://example.org/listing/1", agency="idealista.it")), "html.parser"
    )
    assert publisher_references(soup.select(".result-item"), "101")[0].publisher == "example.org"


def test_references_union_across_pages_without_downstream_requests():
    class HTTP:
        calls = []

        def get(self, url):
            self.calls.append(url)
            if "/city.jsp?" in url:
                return b'{"id":"firenze","name":"Firenze","province":"FI","region":"toscana"}'
            publisher = "idealista.it" if "page=2" in url else "immobiliare.it"
            return (
                page(link(f"https://www.{publisher}/listing/1"))
                + f'<a href="{SEARCH}&page=2">2</a>'
            ).encode()

        def post_form(self, url, data):
            self.calls.append(url)
            return ('{"canonical":"' + SEARCH + '"}').encode()

    http = HTTP()
    results = CaasaAdapter(http).search(43.779, 11.246, 2000)
    assert len(results) == 1 and len(results[0].publisher_references) == 2
    assert all(
        urlsplit(url).netloc == "www.caasa.it" and "/ClickTag" not in url for url in http.calls
    )


def test_dedup_preserves_references_but_does_not_merge_unverified_identity():
    a = PublisherReference("idealista.it", "https://www.idealista.it/immobile/1/", "caasa")
    b = PublisherReference("wikicasa.it", "https://www.wikicasa.it/annuncio/2", "caasa")
    listing = Listing("caasa", "101", "Synthetic", publisher_references=(a,))
    rows = deduplicate(
        [
            SearchHit(x, 0, "approximate")
            for x in (
                listing,
                replace(listing, publisher_references=(b,)),
                replace(listing, source_id="102"),
            )
        ]
    )
    assert len(rows) == 2 and len(rows[0].listing.publisher_references) == 2
    report = SearchReport(SearchQuery(43.779, 11.246), "IT", "partial", rows)
    assert report.to_dict()["coverage"]["publisher_references"] == [
        {
            "publisher": "idealista.it",
            "matched_listings": 2,
            "distinct_urls": 1,
            "observed_via": ["caasa"],
            "verification": "not_fetched",
        },
        {
            "publisher": "wikicasa.it",
            "matched_listings": 1,
            "distinct_urls": 1,
            "observed_via": ["caasa"],
            "verification": "not_fetched",
        },
    ]


def test_cli_exposes_attribution_without_marking_portal_queried(monkeypatch, capsys):
    class Adapter:
        warnings = []

        def search(self, *args):
            return [
                Listing(
                    "caasa",
                    "101",
                    "Synthetic",
                    latitude=43.779,
                    longitude=11.246,
                    location_precision="approximate",
                    publisher_references=(
                        PublisherReference(
                            "idealista.it", "https://www.idealista.it/immobile/1/", "caasa"
                        ),
                    ),
                )
            ]

    monkeypatch.setattr(Registry, "load", lambda *args: Adapter())
    assert main(["search", "--lat", "43.779", "--lon", "11.246", "--source", "caasa"]) == 0
    out = capsys.readouterr().out
    assert "Publisher idealista.it: 1 returned listings" in out
    assert "Publisher reference via caasa (not fetched)" in out
