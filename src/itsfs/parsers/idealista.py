"""Normalize an already obtained Italian Idealista residential detail DOM.

This module does not acquire pages, operate browsers or register a live source.
The capture time is required so replaying an old page cannot make it look fresh.
"""

import re
from datetime import datetime
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from itsfs.adapters.base import SourceChanged
from itsfs.adapters.italy.demanio import italian_number
from itsfs.models import Listing

RESIDENTIAL = {
    "appartamento",
    "monolocale",
    "bilocale",
    "trilocale",
    "quadrilocale",
    "attico",
    "villa",
    "casa indipendente",
}


def parse_detail(body: str | bytes, url: str, *, captured_at: datetime) -> Listing:
    """Read observed factual labels; reject unreviewed categories and transactions."""
    p = urlsplit(url)
    match = re.fullmatch(r"/immobile/([0-9]+)/", p.path)
    if p.scheme != "https" or p.netloc != "www.idealista.it" or not match or p.query or p.fragment:
        raise ValueError("expected a canonical Italian Idealista listing URL")
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ValueError("capture time must be timezone-aware")
    soup = BeautifulSoup(body, "html.parser")
    heading = soup.select_one("h1 .main-info__title-main")
    features = soup.select_one(".details-property-feature-one")
    if heading is None or features is None:
        raise SourceChanged("Idealista detail structure missing; not a recognized listing page")
    title = heading.get_text(" ", strip=True)
    sale = re.fullmatch(r"(.+?) in vendita in (.+)", title, re.I)
    if not sale or sale[1].casefold() not in RESIDENTIAL:
        raise SourceChanged("only reviewed residential sale titles are supported")
    if re.search(r"\basta\b|\bvenduto\b|non pi[uù] disponibile", title, re.I):
        raise SourceChanged("not a supported current asking-price sale")

    price = area = usable = rooms = bathrooms = None
    notes = []
    prices = []
    for row in soup.select("p.flex-feature"):
        label = row.select_one("span.flex-feature-details")
        value = row.select_one("strong.flex-feature-details")
        if label and label.get_text(" ", strip=True) == "Prezzo dell'immobile:" and value:
            prices.append(value.get_text(" ", strip=True))
    if len(set(prices)) > 1:
        raise SourceChanged("conflicting Idealista asking prices")
    if prices:
        try:
            if not prices[0].endswith("€"):
                raise ValueError
            price = italian_number(prices[0][:-1])
        except ValueError:
            notes.append("unrecognized asking price; retained as null")
    for li in features.select("li"):
        text = li.get_text(" ", strip=True)
        if m := re.fullmatch(r"([\d.,]+) m² commerciali(?:, ([\d.,]+) m² calpestabili)?", text):
            try:
                area = italian_number(m[1])
                usable = italian_number(m[2])
            except ValueError:
                area = usable = None
                notes.append("unrecognized floor area; retained as null")
        elif m := re.fullmatch(r"(\d+) locali?", text):
            rooms = int(m[1])
        elif m := re.fullmatch(r"(\d+) bagn[oi]", text):
            bathrooms = int(m[1])

    # Only the observed five-line layout is understood; no town-point invention.
    location = [li.get_text(" ", strip=True) for li in soup.select("#headerMap li")]
    address = municipality = None
    if (
        len(location) == 5
        and location[1].startswith("Quartiere ")
        and location[2].startswith("Zona ")
    ):
        address, municipality = location[0], location[3]
    elif location:
        notes.append("unreviewed location layout; address and municipality retained as null")
    return Listing(
        source="idealista",
        source_id=match[1],
        title=title,
        url=url,
        price=price,
        currency="EUR" if price is not None else None,
        property_type="residential",
        area_m2=area,
        address=address,
        municipality=municipality,
        retrieved_at=captured_at,
        raw={
            "acquisition": "supplied_browser_dom",
            "price_kind": "asking_price",
            "availability_basis": "displayed sale advertisement; seller availability unverified",
            "coordinate_basis": "not established from supplied DOM",
            "usable_area_m2": usable,
            "rooms": rooms,
            "bathrooms": bathrooms,
            "parser_warnings": notes,
        },
    )
