from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from itsfs.adapters.base import AccessDenied, SourceChanged
from itsfs.adapters.italy.idealista import IdealistaAdapter, parse_search
from itsfs.browser import BrowserPage, IdealistaBrowser, check_url, municipality_link
from itsfs.models import SearchQuery
from itsfs.registry import Registry
from itsfs.search import SearchEngine

URL = "https://www.idealista.it/vendita-case/firenze-firenze/con-aste_no/"
STAMP = datetime(2026, 9, 15, tzinfo=UTC)


def snapshot():
    return BrowserPage(URL, Path("tests/fixtures/idealista_search.html").read_text(), STAMP)


class FixturePolicy:
    min_interval = 2

    def get(self, url):
        return b""

    def check_policy(self, url):
        self.get(url)

    def close(self):
        pass


class FixtureBrowser:
    def search(self, town):
        assert "firenze" in town["names"]
        return snapshot()


def fixture_adapter():
    return IdealistaAdapter(FixturePolicy(), browser=FixtureBrowser())


def test_factual_normalization_and_unknown_location():
    rows, warnings = parse_search(snapshot())
    assert not warnings
    first, second = rows
    assert first.source == "idealista" and first.price == 245000 and first.area_m2 == 85
    assert first.bedrooms is None and first.raw["rooms"] == 3
    assert first.location_precision == "area_only" and first.retrieved_at == STAMP
    assert first.description is None
    assert second.price is None and second.currency is None and second.latitude is None
    assert second.location_precision == "unknown"


@pytest.mark.parametrize(
    "old,new",
    [
        ('aria-selected="true"', 'aria-selected="false"'),
        ("Escludi aste", "Indifferente"),
        ('id="h1-container"', 'id="new-heading"'),
        ('href="/immobile/90000001/"', 'href="https://evil.example/"'),
        ('data-element-id="90000001"', 'data-element-id="90000009"'),
    ],
)
def test_changed_identity_or_filters_fail(old, new):
    snap = snapshot()
    with pytest.raises(SourceChanged):
        parse_search(replace(snap, body=snap.body.replace(old, new)))


def test_no_cards_is_not_empty_success():
    snap = snapshot()
    with pytest.raises(SourceChanged):
        parse_search(replace(snap, body=snap.body.split("<article")[0]))


def test_genuine_empty_search():
    snap = snapshot()
    assert parse_search(
        replace(snap, body=snap.body.split("<article")[0].replace("2 case", "0 case"))
    ) == ([], [])


def test_dedup_and_offmarket():
    snap = snapshot()
    assert len(parse_search(replace(snap, body=snap.body + snap.body))[0]) == 2
    rows, notes = parse_search(
        replace(snap, body=snap.body.replace('data-is-offmarket=""', 'data-is-offmarket="true"'))
    )
    assert len(rows) == 1 and notes


def test_engine_requires_unlocated_opt_in():
    registry = Registry(http=FixturePolicy())
    registry.enable_idealista_browser()
    registry.instances["idealista"] = fixture_adapter()
    q = SearchQuery(43.77925, 11.24626, 5000)
    engine = SearchEngine(registry)
    assert not engine.search(q, ["idealista"]).results
    report = engine.search(replace(q, include_unlocated=True), ["idealista"])
    assert report.status == "partial" and len(report.results) == 2
    assert all(h.radius_match == "unverified" for h in report.results)
    assert all(h.listing.source == "idealista" for h in report.results)


def test_homepage_and_autocomplete_link_selection():
    home = '<a class="icon-elbow" href="/vendita-case/firenze-firenze/">Firenze</a>'
    assert municipality_link(home, ["firenze"]) == URL.replace("con-aste_no/", "")
    suggestion = (
        '<a href="/vendita-case/firenze-firenze/"><i>Firenze, Firenze</i>'
        '<span class="icon-location-outline">Comune</span></a>'
    )
    assert municipality_link(suggestion, ["firenze"], autocomplete=True)
    assert (
        municipality_link(suggestion.replace("Comune", "Provincia"), ["firenze"], autocomplete=True)
        is None
    )
    with pytest.raises(SourceChanged):
        municipality_link(home + home.replace("firenze-firenze", "other-place"), ["firenze"])


@pytest.mark.parametrize(
    "url",
    [
        "http://www.idealista.it/",
        "https://idealista.it/",
        "https://www.idealista.it@evil.example/",
        "https://www.idealista.it/login",
        "https://www.idealista.it/vendita-case/?token=secret",
    ],
)
def test_browser_url_scope(url):
    with pytest.raises(AccessDenied):
        check_url(url)


def test_policy_denial_prevents_navigation(monkeypatch):
    class Denied(FixturePolicy):
        def check_policy(self, url):
            raise AccessDenied("robots disallows")

    browser = IdealistaBrowser(Denied())
    with pytest.raises(AccessDenied):
        browser._allow(URL)
    assert not browser.navigation_log


def test_interactive_challenge_stops_before_readiness():
    class Locator:
        def count(self):
            return 1

    class Page:
        frames = []

        def locator(self, selector):
            return Locator()

    with pytest.raises(AccessDenied, match="challenge"):
        IdealistaBrowser(FixturePolicy())._ready(Page(), "#h1-container")
