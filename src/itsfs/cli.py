import argparse
import json
import sys

from .geo import parse_radius
from .geocoding import LocalGeocoder
from .models import PROPERTY_TYPES, SearchQuery
from .registry import Registry
from .search import SearchEngine


def clean(text) -> str:
    """Prevent source text from injecting terminal control sequences."""
    return " ".join("".join(c for c in str(text) if c.isprintable() or c.isspace()).split())


def parser():
    root = argparse.ArgumentParser(prog="itsfs", description="Deterministic property search")
    root.add_argument("--version", action="version", version="itsfs 0.1.0")
    commands = root.add_subparsers(dest="command", required=True)
    listing = commands.add_parser("sources", help="show implemented and investigated sources")
    listing.add_argument("--json", action="store_true")
    listing.add_argument("--config")
    search = commands.add_parser("search")
    search.add_argument("--lat", type=float)
    search.add_argument("--lon", type=float)
    search.add_argument("--location", help="offline Italian town name, optionally Province, Italy")
    search.add_argument("--radius", default="1000", help="metres by default; e.g. 500m or 2km")
    search.add_argument("--country", help="explicit two-letter country override near boundaries")
    search.add_argument("--type", dest="types", action="append", choices=sorted(PROPERTY_TYPES))
    search.add_argument("--source", action="append", help="limit to a named enabled source")
    search.add_argument("--config", help="additional reviewed feed-source JSON configuration")
    search.add_argument(
        "--idealista-browser",
        nargs="?",
        const="playwright",
        choices=["playwright"],
        help="enable Idealista search in fresh bundled Chromium, isolated from personal Chrome",
    )
    search.add_argument(
        "--include-unlocated",
        action="store_true",
        help="include municipality-level/unknown locations; radius is unverified",
    )
    search.add_argument("--json", action="store_true")
    return root


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    registry = Registry()
    try:
        if args.config:
            registry.add_config(args.config)
        if args.command == "sources":
            if args.json:
                print(json.dumps(registry.to_dict(), indent=2))
            else:
                for s in registry.specs:
                    print(
                        f"{s.source:24} {s.status:14} {'enabled' if s.enabled else 'disabled'} "
                        f"{','.join(s.country_codes)} — {s.notes}"
                    )
            return 0
        if args.idealista_browser:
            registry.enable_idealista_browser(args.idealista_browser)
        lat, lon = args.lat, args.lon
        if args.location:
            if lat is not None or lon is not None:
                raise ValueError("use --location or --lat/--lon, not both")
            place = LocalGeocoder().geocode(args.location)
            lat, lon = place.latitude, place.longitude
        elif lat is None or lon is None:
            raise ValueError("provide both --lat and --lon, or --location")
        query = SearchQuery(
            lat, lon, parse_radius(args.radius), args.types, args.country, args.include_unlocated
        )
        report = SearchEngine(registry).search(query, args.source)
        if args.json:
            print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, allow_nan=False))
        else:
            print(
                f"{report.status.upper()} | {report.country or 'unknown country'} | "
                f"{len(report.results)} results | radius {query.radius_m:g} m"
            )
            if report.coverage:
                queried = sum(s["state"] == "queried" for s in report.coverage)
                print(
                    f"Coverage: {queried}/{len(report.coverage)} catalogued sources queried; "
                    "country coverage is incomplete. Run itsfs sources for gaps."
                )
            for hit in report.results:
                x = hit.listing
                price = (
                    f"{x.currency or ''} {x.price:,.0f}" if x.price is not None else "price unknown"
                )
                distance = (
                    f"~{hit.distance_m:,.0f} m"
                    if hit.distance_m is not None
                    else "distance unknown"
                )
                if x.raw.get("price_kind") == "auction_starting_price":
                    price += " starting bid"
                basis = " to town; radius unverified" if hit.radius_match == "unverified" else ""
                if hit.distance_m is None:
                    basis = "; radius unverified"
                print(
                    clean(
                        f"{x.source} | {x.title} | {price} | {x.property_type} | {distance}{basis}"
                    )
                )
                print(clean(x.url or "URL unavailable"))
                for ref in x.publisher_references:
                    print(
                        clean(
                            f"  Publisher reference via {ref.observed_via} (not fetched): {ref.url}"
                        )
                    )
            for row in report.publisher_coverage():
                print(
                    clean(
                        f"Publisher {row['publisher']}: {row['matched_listings']} returned "
                        f"listings, {row['distinct_urls']} URLs; indirect, not fetched"
                    )
                )
            for s in report.sources:
                for warning in s.warnings:
                    print(f"{s.source}: {clean(warning)}", file=sys.stderr)
                if s.error:
                    print(f"{s.source}: {clean(s.error)}", file=sys.stderr)
            for warning in report.warnings:
                print(clean(warning), file=sys.stderr)
        return {"ok": 0, "partial": 0, "unsupported": 3, "error": 4}[report.status]
    except ValueError as exc:
        print(f"itsfs: {clean(exc)}", file=sys.stderr)
        return 2
    finally:
        registry.close()
