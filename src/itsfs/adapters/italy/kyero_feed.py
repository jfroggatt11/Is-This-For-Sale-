from pathlib import Path
from xml.etree.ElementTree import ParseError

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

from itsfs.adapters.base import PropertySourceAdapter, SourceChanged, SourceError
from itsfs.http import MAX_BYTES, PoliteHTTP
from itsfs.models import Listing, SearchQuery

TYPE_MAP = {
    "apartment": "residential",
    "appartamento": "residential",
    "villa": "residential",
    "house": "residential",
    "town house": "residential",
    "country house": "residential",
    "land": "land",
    "terreno": "land",
    "plot": "land",
    "land/ruin": "land",
    "commercial": "commercial",
    "commercial property": "commercial",
    "office": "commercial",
    "hotel": "commercial",
    "shop": "commercial",
    "farm": "agricultural",
    "agricultural land": "agricultural",
    "vineyard": "agricultural",
    "warehouse": "industrial",
    "industrial": "industrial",
    "garage": "garage",
    "building plot": "development",
    "development": "development",
    "mixed": "mixed",
}


def localized(node, path):
    for language in ("it", "en"):
        if text := node.findtext(f"{path}/{language}"):
            return text.strip()
    parent = node.find(path)
    if parent is not None:
        for child in parent:
            if child.text and child.text.strip():
                return child.text.strip()
    return None


def numeric(node, path, *, zero_missing=False, integer=False):
    text = node.findtext(path)
    if not text or not text.strip():
        return None
    value = float(text)
    if zero_missing and value == 0:
        return None
    if integer:
        if not value.is_integer():
            raise ValueError("noninteger bedroom count")
        return int(value)
    return value


class KyeroFeedAdapter(PropertySourceAdapter):
    country_codes = ["IT"]

    def __init__(self, source_name: str, location: str, http: PoliteHTTP):
        super().__init__()
        self.source_name, self.location, self.http = source_name, location, http

    def parse(self, body: bytes) -> list[Listing]:
        try:
            root = ElementTree.fromstring(body, forbid_dtd=True)
        except (ParseError, DefusedXmlException):
            raise SourceChanged("invalid or unsafe Kyero XML") from None
        if root.tag != "root" or root.findtext("kyero/feed_version") != "3":
            raise SourceChanged("expected Kyero root/feed_version 3")
        if any(child.tag not in {"kyero", "property"} for child in root):
            raise SourceChanged("unexpected Kyero root children")
        listings = []
        for node in root.findall("property"):
            if node.findtext("country", "").strip().casefold() not in {"it", "italy", "italia"}:
                continue
            if node.findtext("price_freq", "").strip() != "sale":
                continue
            try:
                kind = node.findtext("type", "").strip()
                category = TYPE_MAP.get(kind.casefold(), "other")
                town = node.findtext("town") or None
                lat = numeric(node, "location/latitude", zero_missing=True)
                lon = numeric(node, "location/longitude", zero_missing=True)
                if lat is None or lon is None:
                    lat = lon = None
                area_key = (
                    "plot" if category in {"land", "agricultural", "development"} else "built"
                )
                listings.append(
                    Listing(
                        source=self.source_name,
                        source_id=node.findtext("id", "").strip(),
                        title=f"{kind or 'Property'} — {town or 'Italy'}",
                        url=localized(node, "url"),
                        price=numeric(node, "price", zero_missing=True),
                        currency=node.findtext("currency") or "EUR",
                        property_type=category,
                        latitude=lat,
                        longitude=lon,
                        location_precision="approximate" if lat is not None else "unknown",
                        area_m2=numeric(node, f"surface_area/{area_key}", zero_missing=True),
                        bedrooms=numeric(node, "beds", zero_missing=True, integer=True),
                        municipality=town,
                        description=localized(node, "desc"),
                        raw={
                            "source_property_type": kind,
                            "source_updated_at": node.findtext("date"),
                            "part_ownership": node.findtext("part_ownership", "0") == "1",
                            "leasehold": node.findtext("leasehold", "0") == "1",
                        },
                    )
                )
            except (ValueError, TypeError, OverflowError):
                self.warnings.append("malformed Kyero sale record skipped")
        return listings

    def search(self, latitude, longitude, radius_m, property_types=None):
        SearchQuery(latitude, longitude, radius_m, property_types)
        self.warnings = []
        if self.location.startswith("https://"):
            body = self.http.get(self.location)
        else:
            try:
                with Path(self.location).open("rb") as stream:
                    body = stream.read(MAX_BYTES + 1)
            except OSError:
                raise SourceError("cannot read local Kyero feed") from None
        if len(body) > MAX_BYTES:
            raise SourceError("feed exceeds the 10 MiB limit")
        return [
            x for x in self.parse(body) if not property_types or x.property_type in property_types
        ]
