from .adapters.base import SourceError
from .dedup import deduplicate
from .geo import detect_country, distance_m
from .models import SearchHit, SearchQuery, SearchReport, SourceOutcome


class SearchEngine:
    def __init__(self, registry):
        self.registry = registry

    def search(self, query: SearchQuery, sources: list[str] | None = None) -> SearchReport:
        country = query.country or detect_country(query.latitude, query.longitude)
        report = SearchReport(query, country, "unsupported")
        entries = self.registry.relevant(country, query.property_types, sources)
        if not entries:
            report.warnings.append(
                "No enabled sources cover this country/type; see discovery docs."
            )
            return report
        hits = []
        for entry in entries:
            try:
                adapter = self.registry.load(entry)
                listings = adapter.search(
                    query.latitude,
                    query.longitude,
                    query.radius_m,
                    list(query.property_types) if query.property_types else None,
                )
                outcome = SourceOutcome(entry.source, "ok", len(listings), list(adapter.warnings))
                local_hits, unlocated = [], 0
                for listing in listings:
                    if query.property_types and listing.property_type not in query.property_types:
                        continue
                    d = None
                    if listing.latitude is not None:
                        d = distance_m(
                            query.latitude, query.longitude, listing.latitude, listing.longitude
                        )
                    uncertain = listing.location_precision in {"area_only", "unknown"} or d is None
                    if uncertain and not query.include_unlocated:
                        unlocated += 1
                        continue
                    if d is not None and d > query.radius_m:
                        continue
                    match = (
                        "unverified"
                        if uncertain
                        else "within_radius"
                        if listing.location_precision == "exact"
                        else "approximate"
                    )
                    local_hits.append(SearchHit(listing, d, match))
                if unlocated:
                    outcome.warnings.append(
                        f"{unlocated} area-only/unlocated candidates excluded; "
                        "use --include-unlocated to inspect uncertain matches"
                    )
                if outcome.warnings:
                    outcome.status = "partial"
                hits.extend(local_hits)
            except SourceError as exc:
                outcome = SourceOutcome(entry.source, "error", error=str(exc))
            except Exception:
                # Third-party code can throw anything, including messages containing tokens.
                outcome = SourceOutcome(entry.source, "error", error="unexpected adapter failure")
            report.sources.append(outcome)
        hits.sort(
            key=lambda h: (
                h.radius_match == "unverified",
                h.distance_m is None,
                h.distance_m or 0,
                h.listing.source,
                h.listing.source_id,
            )
        )
        report.results = deduplicate(hits)
        states = {s.status for s in report.sources}
        report.status = "error" if states == {"error"} else "ok" if states == {"ok"} else "partial"
        return report
