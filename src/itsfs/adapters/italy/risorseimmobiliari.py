"""Bounded residential searches on reviewed public province catalogues."""

import json
import re
from importlib.resources import files
from urllib.parse import parse_qs, urljoin, urlsplit

from bs4 import BeautifulSoup

from itsfs.adapters.base import AccessDenied, PropertySourceAdapter, SourceChanged, SourceError
from itsfs.adapters.italy.demanio import italian_number
from itsfs.geo import distance_m
from itsfs.geocoding import LocalGeocoder, towns
from itsfs.models import Listing, SearchQuery, coordinates

BASE = "https://www.risorseimmobiliari.it"
TYPE_MAP = dict.fromkeys(
    [
        "Appartamento",
        "Appartamento indipendente",
        "Attico",
        "Bifamiliare",
        "Bungalow / Piazzola",
        "Casa semi indipendente",
        "Casa singola",
        "Colonica",
        "Dammuso",
        "Loft",
        "Mansarda",
        "Masseria",
        "Multiproprietà",
        "Nuova costruzione",
        "Open space",
        "Palazzo",
        "Rustico casale",
        "Stanza / Camera",
        "Tenuta-Complesso",
        "Terratetto",
        "Trulli",
        "Villa",
        "Villa a schiera",
        "Villino",
    ],
    "residential",
)
TYPE_MAP.update({"Garage / Posto auto": "garage", "Cantina": "other"})


def province_paths(latitude, longitude, radius_m):
    routes = json.loads(files("itsfs").joinpath("data/risorse_provinces.json").read_text())
    distances = {}
    for town in towns():
        code = town["province"]
        if code in routes:
            d = distance_m(latitude, longitude, town["lat"], town["lon"])
            distances[code] = min(d, distances.get(code, float("inf")))
    ordered = sorted(distances, key=distances.get)
    return [routes[c] for c in ordered if distances[c] <= radius_m + 20_000][:3]


class RisorseimmobiliariAdapter(PropertySourceAdapter):
    source_name = "risorseimmobiliari"
    country_codes = ["IT"]

    def __init__(self, http, *, max_pages=2, max_details=12, geocoder=None):
        super().__init__()
        if not 1 <= max_pages <= 5 or not 1 <= max_details <= 40:
            raise ValueError("max_pages must be 1..5; max_details must be 1..40")
        self.http = http
        self.max_pages, self.max_details = max_pages, max_details
        self.geocoder = geocoder or LocalGeocoder()

    @staticmethod
    def parse_search(body, url):
        soup = BeautifulSoup(body, "html.parser")
        form = soup.select_one("form#ricerca")
        count = re.search(r"([\d.]+)\s+annunci trovati", soup.get_text(" ", strip=True))
        if form is None or not count:
            raise SourceChanged("unrecognized RisorseImmobiliari catalogue")
        sale = form.select_one("#tipo_contratto option[selected]")
        if sale is None or sale.get("value") != "V":
            raise SourceChanged("RisorseImmobiliari catalogue lost sale filter")
        urls = []
        for card in soup.select("article.annuncio .property-item"):
            sid, path = card.get("data-codann", ""), card.get("data-permalink", "")
            target = urljoin(BASE, path)
            if (
                not sid.isdigit()
                or urlsplit(target).netloc != urlsplit(BASE).netloc
                or not re.fullmatch(
                    r"/[^/]+/vendita-[^/]+-" + re.escape(sid) + r"\.html", urlsplit(target).path
                )
            ):
                raise SourceChanged("unrecognized RisorseImmobiliari sale identity")
            if target not in urls:
                urls.append(target)
        if int(count[1].replace(".", "")) and not urls:
            raise SourceChanged("RisorseImmobiliari count has no recognized sale cards")
        current = urlsplit(url)
        stem = re.sub(r"(?:_pag\d+)?\.html$", "", current.path)
        page_match = re.search(r"_pag(\d+)\.html$", current.path)
        page = int(page_match[1]) if page_match else 1
        next_url = None
        for a in soup.select(".pagination a[href]"):
            target = urljoin(BASE, a["href"])
            p = urlsplit(target)
            if p.path == f"{stem}_pag{page + 1}.html":
                if p.netloc != current.netloc or parse_qs(p.query) != {"cod_categoria": ["R"]}:
                    raise SourceChanged("RisorseImmobiliari pagination changed filters")
                next_url = target
        return urls, next_url

    def parse_detail(self, body, url):
        soup = BeautifulSoup(body, "html.parser")
        fields = {}
        for label in soup.select("label"):
            span = label.find_next_sibling("span")
            if span:
                fields[label.get_text(" ", strip=True)] = span.get_text(" ", strip=True)
        if not {"Contratto", "Tipologia", "Comune"} <= fields.keys():
            raise SourceChanged("unrecognized RisorseImmobiliari detail fields")
        if fields["Contratto"] != "Vendita" or fields.get("Stato", "").casefold() in {
            "venduto",
            "ritirato",
            "scaduto",
        }:
            return None
        if not soup.h1 or re.search(r"\b(venduto|ritirato|scaduto)\b", soup.h1.get_text(), re.I):
            return None

        def number(key):
            value = fields.get(key)
            if not value or "riservat" in value.casefold():
                return None
            value = re.sub(r"(?:€|m\s*2|mq|locali)", "", value).strip()
            try:
                return italian_number(value)
            except ValueError:
                self.warnings.append(f"unrecognized RisorseImmobiliari {key}; retained as null")
                return None

        lat = lon = None
        precision = "unknown"
        lat_node, lon_node = (
            soup.select_one('[itemprop="latitude"]'),
            soup.select_one('[itemprop="longitude"]'),
        )
        if lat_node or lon_node:
            try:
                lat = float(lat_node.get_text(strip=True))
                lon = float(lon_node.get_text(strip=True))
                coordinates(lat, lon)
                if (lat, lon) == (0, 0):
                    raise ValueError("placeholder point")
                precision = "approximate"
            except (ValueError, AttributeError):
                self.warnings.append(
                    "invalid property map coordinates; using municipality if available"
                )
                lat = lon = None
        if lat is None:
            place = self.geocoder.municipality(fields["Comune"])
            if place:
                lat, lon, precision = place.latitude, place.longitude, "area_only"
        bedrooms = number("Camere")
        if bedrooms is not None and not bedrooms.is_integer():
            bedrooms = None
            self.warnings.append("fractional bedrooms retained as null")
        return Listing(
            source=self.source_name,
            source_id=re.search(r"-(\d+)\.html$", url)[1],
            url=url,
            title=f"{fields['Tipologia']} a {fields['Comune']}",
            price=number("Prezzo") if "€" in fields.get("Prezzo", "") else None,
            currency="EUR" if "€" in fields.get("Prezzo", "") else None,
            property_type=TYPE_MAP.get(fields["Tipologia"], "other"),
            latitude=lat,
            longitude=lon,
            location_precision=precision,
            area_m2=number("Superficie"),
            bedrooms=int(bedrooms) if bedrooms is not None else None,
            municipality=fields["Comune"],
            raw={
                "price_kind": "asking_price",
                "source_property_type": fields["Tipologia"],
                "source_date": fields.get("Data annuncio"),
                "availability_basis": "public sale advertisement; confirm with publisher",
                "coordinate_basis": "provider property map"
                if precision == "approximate"
                else "municipality or unavailable",
            },
        )

    def search(self, latitude, longitude, radius_m, property_types=None):
        SearchQuery(latitude, longitude, radius_m, property_types)
        self.warnings = [
            "Residential catalogue only; nearby-town province routing and request caps "
            "can miss listings."
        ]
        if property_types and not set(property_types) & {"residential", "garage", "other"}:
            return []
        results, seen = [], set()
        for path in province_paths(latitude, longitude, radius_m):
            url, visited = BASE + path, set()
            for _ in range(self.max_pages):
                if url in visited:
                    self.warnings.append("pagination repeated a page; stopped")
                    break
                visited.add(url)
                body = self.http.get(url)
                urls, next_url = self.parse_search(body, url)
                new = [u for u in urls if u not in seen]
                if urls and not new:
                    self.warnings.append("pagination repeated listings; stopped")
                    break
                # Prioritize visible property map points near the query without executing JS.
                points = {}
                for lat, lon, path, sid in re.findall(
                    r",\s*(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?),\s*'(/[^']+\.html)',\s*(\d+)\s*\]",
                    body.decode("utf-8", errors="replace"),
                ):
                    if path.endswith(f"-{sid}.html"):
                        points[urljoin(BASE, path)] = (float(lat), float(lon))

                def proximity(target, points=points):
                    point = points.get(target)
                    return distance_m(latitude, longitude, *point) if point else float("inf")

                new.sort(key=proximity)
                for detail in new:
                    if len(seen) >= self.max_details:
                        self.warnings.append("detail request limit reached; coverage is incomplete")
                        return results
                    seen.add(detail)
                    try:
                        item = self.parse_detail(self.http.get(detail), detail)
                    except AccessDenied:
                        raise
                    except SourceError as exc:
                        self.warnings.append(str(exc))
                        continue
                    if item and (not property_types or item.property_type in property_types):
                        results.append(item)
                if not next_url:
                    break
                url = next_url
            else:
                self.warnings.append("page limit reached; coverage is incomplete")
        return results
