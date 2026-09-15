"""Bounded, opt-in Caasa provenance probe. Run after pip install -e .

python scripts/probe_publishers.py > docs/publisher-probe-live.json
Only Caasa is requested. No original publisher, tracker or account requests.
"""

import json
from dataclasses import asdict
from datetime import UTC, datetime
from urllib.parse import urlsplit

from itsfs.adapters.italy.caasa import CaasaAdapter
from itsfs.geocoding import LocalGeocoder
from itsfs.http import PoliteHTTP
from itsfs.models import SearchQuery
from itsfs.registry import Registry
from itsfs.search import SearchEngine


class AuditedHTTP(PoliteHTTP):
    def __init__(self):
        super().__init__("IsThisForSale/0.1 (bounded public publisher attribution review)")
        self.requests = []

    def _request(self, url, **kwargs):
        if urlsplit(url).hostname != "www.caasa.it" or "/ClickTag" in url:
            raise AssertionError("probe must never fetch publishers or click trackers")
        self.requests.append(
            {"method": "POST" if kwargs.get("data") is not None else "GET", "url": url}
        )
        return super()._request(url, **kwargs)


def main():
    http = AuditedHTTP()
    registry = Registry(http=http)
    registry.instances["caasa"] = CaasaAdapter(http, max_cities=1, max_pages=2)
    output = {
        "started_at": datetime.now(UTC).isoformat(),
        "limits": {
            "max_cities_per_query": 1,
            "max_pages_per_city": 2,
            "radius_m": 5000,
            "property_types": ["residential"],
            "exhaustive": False,
        },
        "queries": [],
    }
    try:
        for name in ["Firenze, FI", "Milano, MI", "Roma, RM"]:
            place = LocalGeocoder().geocode(name)
            query = SearchQuery(place.latitude, place.longitude, 5000, ("residential",))
            report = SearchEngine(registry).search(query, ["caasa"])
            output["queries"].append(
                {
                    "location": name,
                    "query": asdict(query),
                    "status": report.status,
                    "matched_listings": len(report.results),
                    "publisher_references": report.publisher_coverage(),
                    "sources": [asdict(s) for s in report.sources],
                    "evidence": [
                        {
                            "caasa_id": h.listing.source_id,
                            "caasa_url": h.listing.url,
                            "retrieved_at": h.listing.retrieved_at.isoformat(),
                            "radius_match": h.radius_match,
                            "distance_m": h.distance_m,
                            "references": [asdict(r) for r in h.listing.publisher_references],
                        }
                        for h in report.results
                    ],
                }
            )
            if report.status == "error":
                # In particular, never issue more queries after access denial.
                break
    finally:
        registry.close()
    output["requests"] = http.requests
    output["finished_at"] = datetime.now(UTC).isoformat()
    print(json.dumps(output, indent=2, ensure_ascii=False, allow_nan=False))
    return 1 if any(q["status"] == "error" for q in output["queries"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
