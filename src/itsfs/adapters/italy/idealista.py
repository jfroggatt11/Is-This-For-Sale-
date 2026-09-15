"""Direct browser search of a bounded Italian residential sale catalogue."""

import re
from dataclasses import replace

from bs4 import BeautifulSoup

from itsfs.adapters.base import PropertySourceAdapter, SourceChanged
from itsfs.adapters.italy.demanio import italian_number
from itsfs.browser import IdealistaBrowser, check_url
from itsfs.geo import distance_m
from itsfs.geocoding import LocalGeocoder, towns
from itsfs.models import Listing, SearchQuery
from itsfs.parsers.idealista import RESIDENTIAL


def parse_search(snapshot, *, geocoder=None):
    check_url(snapshot.url)
    if not re.fullmatch(
        r"https://www\.idealista\.it/vendita-case/[^/]+/con-aste_no/", snapshot.url
    ):
        raise SourceChanged("Idealista search lacks the reviewed sale/auction filters")
    soup = BeautifulSoup(snapshot.body, "html.parser")
    heading = soup.select_one("#h1-container")
    sale = soup.select_one('#tab-buy[aria-selected="true"]')
    auction = soup.select_one("#qa_adfilter_auctionability .placeholder")
    count = re.search(
        r"([\d.]+) case in vendita", heading.get_text(" ", strip=True) if heading else ""
    )
    if (
        not count
        or sale is None
        or auction is None
        or auction.get_text(strip=True) != "Escludi aste"
    ):
        raise SourceChanged("Idealista catalogue structure or active sale filters changed")
    cards = soup.select("article.item[data-element-id]")
    if int(count[1].replace(".", "")) and not cards:
        raise SourceChanged("Idealista reports inventory but has no recognized listing cards")
    geocoder = geocoder or LocalGeocoder()
    results, warnings, seen = [], [], set()
    for card in cards[:30]:
        sid = card.get("data-element-id", "")
        link = card.select_one("a.item-link")
        if not sid.isdigit() or link is None or link.get("href") != f"/immobile/{sid}/":
            raise SourceChanged("Idealista listing identity changed")
        if sid in seen:
            continue
        seen.add(sid)
        title = link.get_text(" ", strip=True)
        if card.get("data-is-offmarket") or re.search(
            r"\basta\b|\bvenduto\b", card.get_text(" "), re.I
        ):
            warnings.append("excluded auction/off-market card")
            continue
        if not any(title.casefold().startswith(kind + " in ") for kind in RESIDENTIAL):
            warnings.append("unreviewed residential title family skipped")
            continue
        node = card.select_one(".item-price")
        price = area = rooms = None
        try:
            text = node.get_text(" ", strip=True) if node else ""
            if text.endswith("€"):
                price = italian_number(text[:-1])
        except ValueError:
            warnings.append("unrecognized asking price; retained as null")
        for detail in card.select(".item-detail"):
            text = detail.get_text(" ", strip=True)
            if m := re.fullmatch(r"([\d.,]+) m²", text):
                try:
                    area = italian_number(m[1])
                except ValueError:
                    warnings.append("unrecognized area; retained as null")
            elif m := re.fullmatch(r"(\d+) locali?", text):
                rooms = int(m[1])
        # A town point is only a fallback; never call it a property point.
        municipality = title.rsplit(",", 1)[-1].strip() if "," in title else None
        place = geocoder.municipality(municipality) if municipality else None
        listing = Listing(
            source="idealista",
            source_id=sid,
            title=title,
            url=f"https://www.idealista.it/immobile/{sid}/",
            property_type="residential",
            price=price,
            currency="EUR" if price is not None else None,
            area_m2=area,
            municipality=municipality if place else None,
            retrieved_at=snapshot.captured_at,
            raw={
                "acquisition": "direct_browser_dom",
                "search_url": snapshot.url,
                "price_kind": "asking_price",
                "rooms": rooms,
                "availability_basis": "sale advertisement; seller availability unverified",
                "coordinate_basis": "municipality gazetteer" if place else "not established",
            },
        )
        if place:
            listing = replace(
                listing,
                latitude=place.latitude,
                longitude=place.longitude,
                location_precision="area_only",
            )
        results.append(listing)
    return results, warnings


class IdealistaAdapter(PropertySourceAdapter):
    source_name = "idealista"
    country_codes = ["IT"]

    def __init__(self, http, *, browser=None, backend="playwright"):
        super().__init__()
        self.http = http
        if backend != "playwright":
            raise ValueError(
                "only fresh isolated Chromium is supported; shared browser bridge retired"
            )
        self.browser = browser or IdealistaBrowser(http)

    def search(self, latitude, longitude, radius_m, property_types=None):
        SearchQuery(latitude, longitude, radius_m, property_types)
        self.warnings = []
        if property_types and "residential" not in property_types:
            return []
        town = min(towns(), key=lambda t: distance_m(latitude, longitude, t["lat"], t["lon"]))
        self.http.check_policy("https://www.idealista.it/")
        snapshot = self.browser.search(town)
        results, warnings = parse_search(snapshot)
        self.warnings = warnings + [
            "First page of the nearest resolved municipality only; coverage is incomplete.",
            "Town locations require --include-unlocated; property radius cannot be verified.",
            "Residential sales; auctions excluded. No pagination (robots restriction).",
        ]
        return results
