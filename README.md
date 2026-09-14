# Is This For Sale

A small, open-source Python package for deterministic property search around a
point. Agents discover and maintain source adapters; ordinary searches do not
call an LLM. No web app, database, hosted service, or autonomous agent execution.

**v0.1 ships one live, key-free Italian source:** Agenzia del Demanio's public
state-property sale catalogue. It supports residential, land, agricultural and
commercial candidates. It is a narrow government-sale source, not comprehensive
coverage of the Italian market. The package also includes an optional Kyero XML
format adapter for authorized feeds and a fully offline multi-source example.

## Install and search

Python 3.11 or newer:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'

itsfs sources
itsfs search --lat 40.553 --lon 14.218 --radius 1000
itsfs search --location "Anacapri, Italy" --radius 2km
```

The coordinate and town-name commands need **no API key**. Location lookup uses a
bundled Italian GeoNames gazetteer (11,856 town records), not an external service.
Names may also include a province code, e.g. `Firenze, FI, Italy`. Unknown or
ambiguous names require coordinates or a province qualifier.

### A live search that returns inspectable candidates

```bash
itsfs search --location "Firenze, Italy" --radius 10km \
  --type commercial --include-unlocated

itsfs search --location "Firenze, Italy" --radius 10km \
  --type commercial --include-unlocated --json
```

The Demanio pages inspected expose addresses but no property coordinates.
Their town points are labelled **`area_only`**. Strict searches exclude such
listings; `--include-unlocated` admits them with **`radius_match: unverified`**.
A displayed distance then means distance to the town point, never proof that
the property lies in the circle. Unknown coordinates are also admitted by this
flag and may only be relevant at the searched region level. Empty output does
not establish that nothing is for sale.

[The live demonstration](docs/DEMO.md) records a Florence commercial lot and its
limitations. Offer deadlines and award status are checked; auction starting
prices are distinguished from ordinary asking prices. Availability can change.

## Package API

```python
from itsfs import SearchEngine, SearchQuery
from itsfs.registry import Registry

registry = Registry()
try:
    report = SearchEngine(registry).search(SearchQuery(
        latitude=43.77925, longitude=11.24626, radius_m=10_000,
        property_types=("commercial",), include_unlocated=True,
    ))
    for hit in report.results:
        print(hit.listing.title, hit.distance_m, hit.radius_match)
    print(report.status, report.sources)
finally:
    registry.close()
```

`Listing` carries optional price/currency, WGS84 coordinates, precision, area,
bedrooms, address, municipality, description, UTC retrieval timestamp and selected
raw metadata. Taxonomy: `residential`, `land`, `commercial`, `agricultural`,
`industrial`, `garage`, `development`, `mixed`, `other`. Unknown types remain
`other`; unsupported source categories are not invented.

Repeat `--type` or `--source` to select multiple values. `--country IT` overrides
offline containment near borders/islands. Radius accepts metres, `m` or `km`,
including fractions, up to 200 km. Only adapters for the centre country run;
cross-border coverage is not implemented.

JSON output is a report with `query`, `country`, `status`, `results`, `sources`
and `warnings`. Diagnostics stay in JSON for `--json`; text mode sends warnings
to stderr. Exit codes: 0 = completed (possibly partial; inspect status),
2 = invalid input/config, 3 = no applicable enabled adapter, 4 = all sources failed.

## Reproducible offline demo

```bash
itsfs search --location "Anacapri, Italy" --radius 2km \
  --config examples/synthetic-sources.json \
  --source demo_agency_a --source demo_agency_b --json
```

This explicit fixture example demonstrates residential/land/commercial
normalization, multiple providers, distances and deduplication. It contains
**fictional listings**, never used as a fallback for failed live requests.

## Design

```text
src/itsfs/
  models.py             Listing, queries, hits and per-source outcomes
  search.py             failure isolation, filtering, distance ranking
  registry.py           JSON metadata and explicit adapter factories
  geo.py                offline country containment and regional selection
  geocoding.py           replaceable Geocoder protocol + local Italian towns
  dedup.py              conservative IDs/URLs; duplicate provenance retained
  http.py               robots rules, rate limiting, cache and request bounds
  adapters/base.py      source contract and typed errors
  adapters/italy/       Demanio public HTML + optional Kyero feed parser
  data/                 registry and attributed local geographic data
  discovery/            future agent-maintenance workflow
adapter_specs/          pre-implementation access/technical decisions
tests/                  shared conformance, adapter fixtures and optional live tests
docs/                   architecture, source investigation and demonstrations
```

Each source is loaded independently. An import/construction, network, parsing or
normalization failure does not break other sources. Matching first uses source
identity and canonical listing URLs. Similar prices or shared municipality
coordinates do not merge distinct homes. Advanced entity resolution is deferred.

The public source is deliberately bounded: two pages per overlapping region,
20 detail requests total, >=1 second between requests, 20-second HTTP timeout,
10 MiB response cap and five-minute in-process response cache. The containing
region is searched first. Limits, skipped records and uncertain locations produce
partial-coverage diagnostics. No automatic retries, credential discovery,
CAPTCHA handling, proxy rotation, or access-control bypasses.

## Development

```bash
pytest                       # offline; live tests skipped by default
ruff check src tests scripts
ruff format --check src tests scripts
python -m build
ITSFS_LIVE=1 pytest -m live   # optional public requests, no credentials
```

Start with [ADAPTER_SPEC.md](ADAPTER_SPEC.md), [CONTRIBUTING.md](CONTRIBUTING.md)
and [the Italian source investigation](docs/ITALIAN_SOURCES.md). New countries
follow [the agent expansion guide](docs/ADDING_A_COUNTRY_WITH_AN_AGENT.md).
The registry distinguishes working, access-dependent, unavailable and rejected
sources. Investigated sources are not advertised as working integrations.

MIT-licensed code; bundled geography has separate attribution licenses in
[ATTRIBUTION.md](src/itsfs/data/ATTRIBUTION.md). Listing content is not generally
open-licensed; this code license does not grant rights to source inventories.
