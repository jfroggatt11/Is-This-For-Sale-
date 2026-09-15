"""Caasa public location lookup, search URL resolution and structured result facts."""

import json
import math
import re
from dataclasses import replace
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

from bs4 import BeautifulSoup

from itsfs.adapters.base import PropertySourceAdapter, SourceChanged
from itsfs.adapters.italy.demanio import italian_number
from itsfs.geo import distance_m
from itsfs.geocoding import LocalGeocoder
from itsfs.models import Listing, PublisherReference, SearchQuery, coordinates

BASE = "https://www.caasa.it"


def publisher_references(cards, sid):
    """Read advertised destinations from HTML only; never follow click trackers.

    Keep only path-based URLs with no functional query parameters. Unknown URL
    contracts are omitted instead of guessing an identity or retaining tokens.
    The destination hostname is authoritative; Caasa's agency label can differ.
    """
    refs = set()
    for card in cards:
        if card.get("data-id") != sid:
            continue
        for anchor in card.select("a[href]"):
            try:
                tracker = urlsplit(urljoin(BASE, anchor["href"]))
                if tracker.netloc != "www.caasa.it" or tracker.path != "/ClickTag":
                    continue
                query = parse_qs(tracker.query, keep_blank_values=True)
                if query.get("adv") != [sid] or len(query.get("url", [])) != 1:
                    continue
                destination = query["url"][0]
                if any(c.isspace() or ord(c) < 32 for c in destination):
                    continue
                p = urlsplit(destination)
                if not p.hostname or p.path in {"", "/"}:
                    continue
                if any(
                    not k.lower().startswith("utm_")
                    for k in parse_qs(p.query, keep_blank_values=True)
                ):
                    continue
                # No decoding of destination paths or speculative URL rewriting.
                url = p._replace(query="", fragment="").geturl()
                refs.add(PublisherReference(p.hostname.removeprefix("www."), url, "caasa"))
            except (ValueError, TypeError):
                continue
    return tuple(sorted(refs, key=lambda ref: (ref.publisher, ref.url)))


TYPE_MAP = dict.fromkeys(
    [
        "appartamento",
        "attico",
        "baita",
        "bifamiliare",
        "bivano",
        "bungalow",
        "campidanese",
        "caposchiera",
        "casa indipendente",
        "casa semindipendente",
        "casale",
        "dammuso",
        "esavano",
        "intera palazzina",
        "loft",
        "mansarda",
        "maso",
        "monolocale",
        "multiproprieta",
        "multivano",
        "pentavano",
        "quadrivano",
        "trivano",
        "trullo",
        "villa",
        "villetta a schiera",
    ],
    "residential",
)
TYPE_MAP.update(
    {
        "albergo": "commercial",
        "attivita commerciale": "commercial",
        "esercizio commerciale": "commercial",
        "locale commerciale": "commercial",
        "negozio": "commercial",
        "ufficio": "commercial",
        "azienda agricola": "agricultural",
        "terreno agricolo": "agricultural",
        "terreno edificabile": "land",
        "terreno industriale": "land",
        "capannone": "industrial",
        "rudere": "development",
        "locale di sgombero": "other",
    }
)


def object_json(body):
    try:
        value = json.loads(body)
        if not isinstance(value, dict):
            raise ValueError
        return value
    except (ValueError, TypeError):
        raise SourceChanged("unrecognized Caasa JSON response") from None


def city_metadata(value):
    if not isinstance(value, dict) or not all(
        isinstance(value.get(k), str) and value[k] for k in ["id", "name", "province", "region"]
    ):
        raise SourceChanged("unrecognized Caasa municipality")
    return {k: value[k] for k in ["id", "name", "province", "region"]} | {
        "hasBigZones": bool(value.get("hasBigZones", False)),
        "zones": [],
    }


def sale_url(value):
    if not isinstance(value, str):
        raise SourceChanged("missing Caasa sale URL")
    url = urljoin(BASE, value)
    p = urlsplit(url)
    if (
        p.scheme != "https"
        or p.netloc != "www.caasa.it"
        or p.fragment
        or not re.fullmatch(r"/(?:[a-z0-9-]+/){2,3}in-vendita\.html", p.path)
    ):
        raise SourceChanged("unexpected Caasa sale URL")
    if parse_qs(p.query).get("l") != ["e"]:
        raise SourceChanged("Caasa search lost auction exclusion")
    return url


class CaasaAdapter(PropertySourceAdapter):
    source_name = "caasa"
    country_codes = ["IT"]

    def __init__(self, http, *, max_pages=2, max_cities=3, geocoder=None):
        super().__init__()
        if not 1 <= max_pages <= 5 or not 1 <= max_cities <= 5:
            raise ValueError("max_pages and max_cities must be 1..5")
        self.http = http
        self.max_pages, self.max_cities = max_pages, max_cities
        self.geocoder = geocoder or LocalGeocoder()

    def search_url(self, city, types):
        info = city_metadata(city)
        request = {
            "efficencyClass": "G",
            "keywords": {"condition": [], "options": [], "homeType": types},
            "mq": {"smin": 0, "smax": 0},
            "price": {"smin": 0, "smax": 0},
            "legal": "e",
            "location": {
                "province": info.pop("province"),
                "region": info.pop("region"),
                "cities": [info],
            },
        }
        data = object_json(
            self.http.post_form(
                BASE + "/explain.jsp",
                {
                    "advtype": "S",
                    "searchobject": json.dumps(request, separators=(",", ":")),
                },
            )
        )
        return sale_url(data.get("canonical"))

    def parse_listing(self, data, soup, city):
        item, offer = data.get("about"), data.get("offers")
        if not isinstance(item, dict) or not isinstance(offer, dict):
            raise SourceChanged("Caasa property or offer missing")
        sid = str(item.get("identifier", ""))
        if not sid.isdigit():
            raise SourceChanged("Caasa property identifier missing")
        name = offer.get("name", "")
        if not isinstance(name, str) or not name.endswith(" in vendita"):
            return None
        if str(offer.get("availability", "")).rsplit("/", 1)[-1] in {
            "SoldOut",
            "Discontinued",
            "OutOfStock",
        }:
            return None
        card = soup.find(id="ID_" + sid)
        if card and re.search(
            r"(?:propon\w*|offr\w*|disponibile)\s+(?:solo\s+)?in\s+affitto|\baffittasi\b|\ball['’]asta\b",
            card.get_text(" ", strip=True),
            re.I,
        ):
            self.warnings.append(
                "advertisement excluded: sale label conflicts with rental/auction text"
            )
            return None
        url = urljoin(BASE, item.get("url", ""))
        p = urlsplit(url)
        if (
            p.scheme != "https"
            or p.netloc != "www.caasa.it"
            or not re.fullmatch(r"/(?:[a-z0-9-]+/){3}vendita-[0-9a-f]+-opinione\.html", p.path)
            or p.query
            or p.fragment
        ):
            raise SourceChanged("unrecognized Caasa property URL")
        kind = name.removesuffix(" in vendita")
        kinds = {TYPE_MAP.get(k, "other") for k in kind.split(" o ")}
        mapped = next(iter(kinds)) if len(kinds) == 1 else "other"
        address = item.get("address", {})
        if not isinstance(address, dict):
            address = {}
        municipality = address.get("addressLocality")
        lat = lon = None
        precision = "unknown"
        geo = item.get("geo", {})
        if geo:
            try:
                lat, lon = float(geo["latitude"]), float(geo["longitude"])
                coordinates(lat, lon)
                if (lat, lon) == (0, 0):
                    raise ValueError
                precision = "approximate"
                center = city.get("center", {})
                if center and distance_m(lat, lon, center["lat"], center["lng"]) < 1:
                    precision = "area_only"
            except (ValueError, KeyError, TypeError):
                self.warnings.append("invalid Caasa property coordinates; municipality fallback")
                lat = lon = None
        if lat is None and isinstance(municipality, str):
            place = self.geocoder.municipality(municipality, address.get("addressRegion"))
            if place:
                lat, lon, precision = place.latitude, place.longitude, "area_only"

        def number(value, label):
            if value in (None, ""):
                return None
            try:
                if isinstance(value, bool):
                    raise ValueError
                result = float(value)
                if not math.isfinite(result) or result < 0:
                    raise ValueError
                return result
            except (ValueError, TypeError):
                self.warnings.append(f"invalid Caasa {label}; retained as null")
                return None

        currency = offer.get("priceCurrency")
        if not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency):
            currency = None
        floor = item.get("floorSize", {})
        area = (
            number(floor.get("value"), "area")
            if isinstance(floor, dict) and floor.get("unitCode") == "MTK"
            else None
        )
        return Listing(
            source=self.source_name,
            source_id=sid,
            url=url,
            title=f"{kind.capitalize()} a {municipality or city['name']}",
            price=number(offer.get("price"), "price") if currency else None,
            currency=currency,
            property_type=mapped,
            latitude=lat,
            longitude=lon,
            location_precision=precision,
            area_m2=area,
            municipality=municipality,
            address=address.get("streetAddress"),
            raw={
                "price_kind": "asking_price",
                "source_property_type": kind,
                "availability_basis": "public sale advertisement; confirm with publisher",
                "coordinate_basis": "Caasa property map"
                if precision == "approximate"
                else "municipality or unavailable",
            },
        )

    def html_record(self, card):
        marker = card.select_one(".favorite-add[data-advtype][data-canonical]")
        photo = card.select_one(".result-item__image-content img[alt]")
        if marker is None or photo is None:
            raise SourceChanged("Caasa card is missing its identity/type markers")
        if marker["data-advtype"] != "S":
            return None
        match = re.fullmatch(r"(.+?) in vendita a (.+?)(?: in zona .+)?", photo["alt"])
        if not match:
            raise SourceChanged("unrecognized Caasa card type/location")
        item = {
            "identifier": card.get("data-id"),
            "url": marker["data-canonical"],
            "address": {"addressLocality": match[2]},
        }
        offer = {"name": match[1] + " in vendita"}
        price = card.select_one('.result-item__price [title="prezzo"]')
        if price and "€" in price.get_text():
            offer["priceCurrency"] = "EUR"
            try:
                offer["price"] = italian_number(price.get_text().replace("€", "").strip())
            except ValueError:
                self.warnings.append("invalid Caasa price; retained as null")
        for span in card.select(".result-item__price span"):
            text = span.get_text(" ", strip=True)
            if text.startswith("m² "):
                try:
                    item["floorSize"] = {"unitCode": "MTK", "value": italian_number(text[3:])}
                except ValueError:
                    self.warnings.append("invalid Caasa area; retained as null")
        address = card.select_one(".result-item__address a[href]")
        if address:
            item["address"]["streetAddress"] = address.get_text(" ", strip=True)
            point = parse_qs(urlsplit(address["href"]).query).get("q", [""])[0].split(",")
            if len(point) == 2:
                item["geo"] = {"latitude": point[0], "longitude": point[1]}
        return {"about": item, "offers": offer}

    def parse_search(self, body, url, city):
        soup = BeautifulSoup(body, "html.parser")
        title = soup.select_one("#titlesection h1")
        intro = soup.select_one("#titlesection .title-intro")
        if title is None or "in vendita" not in title.get_text().casefold() or intro is None:
            raise SourceChanged("unrecognized Caasa result layout")
        cards = soup.select(".result-item[data-id]")
        if not cards and not (
            "ha trovato 0 annunci" in intro.get_text(" ", strip=True)
            and "Nessun risultato trovato." in soup.get_text()
        ):
            raise SourceChanged("Caasa nonempty result page has no recognized cards")
        results, seen = [], set()
        for card in cards:
            sid = card.get("data-id")
            if sid in seen:
                continue
            node = card.select_one('script[type="application/ld+json"]')
            try:
                data = object_json(node.get_text()) if node else self.html_record(card)
                item = self.parse_listing(data, soup, city) if data else None
                if item:
                    if item.source_id != sid:
                        raise SourceChanged("Caasa structured identity disagrees with card")
                    results.append(
                        replace(item, publisher_references=publisher_references(cards, sid))
                    )
                    seen.add(sid)
            except (SourceChanged, ValueError, TypeError, AttributeError):
                self.warnings.append("malformed Caasa property record excluded")
        current = urlsplit(url)
        filters = parse_qs(current.query)
        page = int(filters.pop("page", ["1"])[0])
        next_url = None
        for a in soup.select("a[href]"):
            target = urljoin(BASE, a["href"])
            p = urlsplit(target)
            q = parse_qs(p.query)
            if q.pop("page", None) == [str(page + 1)] and p.path == current.path:
                if p.netloc != current.netloc or q != filters:
                    raise SourceChanged("Caasa pagination changed filters")
                next_url = sale_url(target)
        return results, next_url

    def search(self, latitude, longitude, radius_m, property_types=None):
        SearchQuery(latitude, longitude, radius_m, property_types)
        self.warnings = [
            "Caasa aggregation is bounded to the query municipality and immediate neighbours; "
            "page/city caps can miss listings."
        ]
        types = [k for k, v in TYPE_MAP.items() if not property_types or v in property_types]
        if not types:
            return []
        # Two seconds also respects the provider's explicitly stated crawler guidance.
        if hasattr(self.http, "min_interval"):
            self.http.min_interval = max(2, self.http.min_interval)
        city = object_json(
            self.http.get(BASE + "/city.jsp?" + urlencode({"lat": latitude, "lng": longitude}))
        )
        city_metadata(city)
        neighbours = city.get("neighbours", [])
        if not isinstance(neighbours, list):
            raise SourceChanged("unrecognized Caasa neighbour list")
        dy = radius_m / 110_000
        dx = dy / max(0.01, math.cos(math.radians(latitude)))
        selected = [city]
        for neighbour in neighbours:
            try:
                bounds = neighbour["bounds"]
                if (
                    bounds["nw"]["lat"] >= latitude - dy
                    and bounds["se"]["lat"] <= latitude + dy
                    and bounds["nw"]["lng"] <= longitude + dx
                    and bounds["se"]["lng"] >= longitude - dx
                ):
                    selected.append(neighbour)
            except (KeyError, TypeError):
                self.warnings.append("invalid neighbour bounds; municipality omitted")
        if len(selected) > self.max_cities:
            self.warnings.append("municipality request limit reached; coverage is incomplete")
        results, seen = {}, set()
        for index, town in enumerate(selected[: self.max_cities]):
            if index:
                if not isinstance(town.get("province"), str) or not isinstance(town.get("id"), str):
                    raise SourceChanged("unrecognized Caasa neighbour identity")
                town = object_json(
                    self.http.get(
                        BASE + "/city.jsp?" + urlencode({"p": town["province"], "c": town["id"]})
                    )
                )
            url = self.search_url(town, types)
            visited = set()
            for _ in range(self.max_pages):
                if url in visited:
                    self.warnings.append("pagination repeated a page; stopped")
                    break
                visited.add(url)
                listings, next_url = self.parse_search(self.http.get(url), url, town)
                new = [x for x in listings if x.source_id not in seen]
                for item in listings:
                    if item.source_id in results:
                        old = results[item.source_id]
                        refs = set(old.publisher_references) | set(item.publisher_references)
                        results[item.source_id] = replace(
                            old,
                            publisher_references=tuple(
                                sorted(refs, key=lambda ref: (ref.publisher, ref.url))
                            ),
                        )
                if listings and not new:
                    self.warnings.append("pagination repeated listings; stopped")
                    break
                for item in new:
                    seen.add(item.source_id)
                    if not property_types or item.property_type in property_types:
                        results[item.source_id] = item
                if not next_url:
                    break
                url = next_url
            else:
                self.warnings.append("page limit reached; coverage is incomplete")
        return list(results.values())
