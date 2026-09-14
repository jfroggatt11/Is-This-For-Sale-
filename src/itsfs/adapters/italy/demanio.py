"""Public government sale pages. Access assessment: adapter_specs/demanio.md."""

import math
import re
from datetime import datetime
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from itsfs.adapters.base import AccessDenied, PropertySourceAdapter, SourceChanged, SourceError
from itsfs.geo import italian_regions
from itsfs.geocoding import LocalGeocoder
from itsfs.http import PoliteHTTP
from itsfs.models import Listing, SearchQuery

BASE = "https://venditaimmobili.agenziademanio.it"
SEARCH = BASE + "/AsteDemanio/sito.php/ricerca/"
ROME = ZoneInfo("Europe/Rome")


def italian_number(text: str | None) -> float | None:
    if not text or not text.strip():
        return None
    match = re.fullmatch(
        r"\s*((?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?)\s*(?:\([^)]*\)|m[q²2]|€)?\s*",
        text,
    )
    if not match:
        raise ValueError("unexpected Italian number")
    value = float(match[1].replace(".", "").replace(",", "."))
    if not math.isfinite(value):
        raise ValueError("nonfinite number")
    return value


def property_type(kind: str, use: str) -> str:
    if use.casefold() == "agricola":
        return "agricultural"
    if kind.casefold() in {"terreni", "terreno"}:
        return "land"
    return {
        "residenziale": "residential",
        "commerciale": "commercial",
        "uffici": "commercial",
        "mista": "mixed",
        "industriale": "industrial",
        "garage": "garage",
    }.get(use.casefold(), "other")


class DemanioAdapter(PropertySourceAdapter):
    source_name = "demanio"
    country_codes = ["IT"]

    def __init__(
        self,
        http: PoliteHTTP,
        *,
        max_pages: int = 2,
        max_details: int = 20,
        now=None,
        geocoder=None,
    ):
        super().__init__()
        if not 1 <= max_pages <= 10 or not 1 <= max_details <= 100:
            raise ValueError("max_pages must be 1..10; max_details must be 1..100")
        self.http = http
        self.max_pages, self.max_details = max_pages, max_details
        self.now = now or (lambda: datetime.now(ROME))
        self.geocoder = geocoder or LocalGeocoder()

    @staticmethod
    def parse_search(body: bytes) -> tuple[list[str], int]:
        soup = BeautifulSoup(body, "html.parser")
        count_node = soup.select_one(".conteggio")
        match = re.search(r"Immobili\s+(\d+)", count_node.get_text(" ") if count_node else "")
        if soup.select_one("form#ricerca") is None or not match:
            raise SourceChanged("unrecognized Demanio search layout")
        urls = []
        for a in soup.select('a[href*="id-immobile="]'):
            url = urljoin(BASE, a["href"])
            p = urlsplit(url)
            ids = parse_qs(p.query).get("id-immobile", [])
            if (
                p.netloc != urlsplit(BASE).netloc
                or p.path != "/AsteDemanio/sito.php/immobile"
                or len(ids) != 1
                or not ids[0].isdigit()
            ):
                raise SourceChanged("unexpected Demanio listing link")
            canonical = BASE + p.path + "?id-immobile=" + ids[0]
            if canonical not in urls:
                urls.append(canonical)
        count = int(match[1])
        if count > 0 and not urls:
            raise SourceChanged("Demanio reports listings but exposes no recognized links")
        return urls, count

    def parse_detail(self, body: bytes, url: str) -> Listing | None:
        soup = BeautifulSoup(body, "html.parser")
        fields = {}
        for row in soup.select("tr"):
            key, value = row.find("th"), row.find("td")
            if key and value:
                fields[key.get_text(" ", strip=True).rstrip(":")] = value.get_text(" ", strip=True)
        required = {"Lotto", "Modalità di Vendita", "Scadenza Offerte", "Tipologia", "Destinazione"}
        if not required <= fields.keys() or not fields["Lotto"]:
            raise SourceChanged("unrecognized Demanio detail fields")
        if not soup.select_one(".badgebando.vendite"):
            raise SourceChanged("Demanio detail is not marked as a sale")
        if fields.get("Prezzo di Aggiudicazione", "").strip():
            return None
        try:
            deadline = fields["Scadenza Offerte"].strip()
            fmt = "%d/%m/%Y ore %H:%M" if "ore" in deadline else "%d/%m/%Y"
            end = datetime.strptime(deadline, fmt).replace(tzinfo=ROME)
        except ValueError:
            self.warnings.append("lot excluded: offer deadline missing or unrecognized")
            return None
        if end <= self.now():
            return None
        address = {}
        for li in soup.select("li.list-group-item"):
            key, sep, value = li.get_text(" ", strip=True).partition(":")
            if sep:
                address[key.strip()] = value.strip()
        municipality = address.get("Comune")
        # Prefer an unambiguous town name; never use the contact person's office address.
        place = self.geocoder.municipality(municipality) if municipality else None

        def optional_number(label):
            try:
                return italian_number(fields.get(label))
            except ValueError:
                self.warnings.append(f"unrecognized Demanio {label}; retained as null")
                return None

        price = optional_number("Prezzo Base")
        area = optional_number("Superficie Lorda")
        return Listing(
            source=self.source_name,
            source_id=parse_qs(urlsplit(url).query)["id-immobile"][0],
            url=url,
            title=fields["Lotto"],
            price=price,
            currency="EUR",
            property_type=property_type(fields["Tipologia"], fields["Destinazione"]),
            latitude=place.latitude if place else None,
            longitude=place.longitude if place else None,
            location_precision="area_only" if municipality else "unknown",
            area_m2=area,
            address=address.get("Via"),
            municipality=municipality,
            raw={
                "price_kind": "auction_starting_price",
                "offer_deadline": end.isoformat(),
                "sale_method": fields["Modalità di Vendita"],
                "region": address.get("Regione"),
                "source_property_type": fields["Tipologia"],
                "source_designation": fields["Destinazione"],
                "coordinate_basis": "GeoNames municipality point" if place else "unavailable",
            },
        )

    def search(self, latitude, longitude, radius_m, property_types=None):
        SearchQuery(latitude, longitude, radius_m, property_types)
        self.warnings = []
        results, seen, calls = [], set(), 0
        for region in italian_regions(latitude, longitude, radius_m):
            for page in range(1, self.max_pages + 1):
                params = {
                    "f_ricerca": "vendite",
                    "f_regione": region,
                    "f_aggiudicati": "-1",
                    "f_datada": self.now().strftime("%d/%m/%Y"),
                    "f_np": page,
                }
                urls, count = self.parse_search(self.http.get(SEARCH + "?" + urlencode(params)))
                new_urls = [u for u in urls if u not in seen]
                if urls and not new_urls:
                    self.warnings.append("pagination repeated a page; stopped")
                    break
                for url in new_urls:
                    if calls >= self.max_details:
                        self.warnings.append("detail request limit reached; coverage is incomplete")
                        return results
                    seen.add(url)
                    calls += 1
                    try:
                        listing = self.parse_detail(self.http.get(url), url)
                    except AccessDenied:
                        raise
                    except SourceError as exc:
                        self.warnings.append(str(exc))
                        continue
                    if listing and (not property_types or listing.property_type in property_types):
                        results.append(listing)
                if page * 10 >= count:
                    break
                if page == self.max_pages:
                    self.warnings.append("page limit reached; coverage is incomplete")
        if results:
            self.warnings.append(
                "Demanio locations are municipality-level; property radius unverified"
            )
        return results
