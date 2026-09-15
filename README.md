# Is This For Sale

A small, open-source Python package for deterministic property search around a
point. Agents discover and maintain source adapters; ordinary searches do not
call an LLM. No web app, database, hosted service, or autonomous agent execution.

**Three live Italian sources run without API keys:** RisorseImmobiliari's agency
sales, Caasa's national portal aggregation, and Agenzia del Demanio's state-property
sales. A combined Florence search returned 45 results within 5 km from the two
private-market sources. [Live evidence and limits](docs/DEMO.md).

The source catalogue tracks **26 candidates**, including restrictions and unfinished
integrations. Country coverage is incomplete and searches are deliberately bounded;
empty output never proves that nothing is for sale. The optional Kyero feed adapter
can add authorized feeds, but no feed access is required or assumed.

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
bundled Italian GeoNames gazetteer (11,856 town records). Source adapters may use
their own public geographic search helpers; Caasa receives the query coordinates.
Names may also include a province code, e.g. `Firenze, FI, Italy`. Unknown or
ambiguous names require coordinates or a province qualifier.

### Combined live search

```bash
itsfs search --location "Firenze, FI" --radius 5km
itsfs search --location "Firenze, FI" --radius 5km --json
itsfs search --location "Firenze, FI" --radius 5km --type commercial --source caasa
```

All applicable enabled sources run by default. JSON includes per-source outcomes
and a `coverage` section showing catalogued sources not searched and why.
Caasa results include publisher references and per-publisher counts, including
major portals when observed. References are attributed to Caasa and marked
`not_fetched`; they do not mean direct portal integration.
[Major-portal access and reproducible measurement](docs/MAJOR_PORTALS.md): the
three-city sample found 62 Idealista, 64 Immobiliare.it and 54 Wikicasa reference
URLs across 84 radius matches; no Casa.it references. Publisher counts overlap.

RisorseImmobiliari and Caasa return approximate property map points where supplied.
Demanio exposes addresses and municipality points, labelled **`area_only`**. Strict
searches exclude area-only/unknown locations; `--include-unlocated` admits these
candidates with **`radius_match: unverified`**. A town-point distance cannot verify
the property's distance. Auction starting prices are distinguished from asking
prices; Demanio deadlines and awards are checked, while Caasa auctions are excluded.

## Direct Idealista browser search (experimental)

Install the optional browser runtime and its separate Chromium browser:

```sh
python -m pip install -e '.[browser]'
python -m playwright install chromium
itsfs search --location 'Firenze, FI' --radius 5km --source idealista \
  --idealista-browser --include-unlocated --json
```

Each search launches bundled Chromium (Chrome for Testing) with a newly created,
empty temporary profile, then closes it and removes that profile. Personal Chrome,
existing profiles, cookies, saved logins and extensions are not used. There is no
attachment endpoint or fallback to an existing browser. No companion installation
or pairing is needed; the former shared-profile extension route is retired.

This path returns up to 30 residential sale cards from one municipality's first
page, excluding auctions, when the site admits the browser. Town locations have
unverified radius matches. Earlier personal Chrome access does not establish
fresh-browser access. The fresh-browser live test returned HTTP 403 and stopped;
[recorded result](docs/idealista-isolated-live.json). Direct extraction in this
fresh environment remains unresolved. A passive follow-up reached an interactive
CAPTCHA on the public search page; no challenge was used.
[Device-check diagnostic](docs/idealista-device-check-live.json).
[Source evidence](adapter_specs/idealista.md).

Run `python scripts/check_browser_isolation.py` to check the actual browser
lifecycle twice against intercepted synthetic pages: empty cookies/local storage,
different temporary profile directories, and profile cleanup. It makes no external
website requests. [Recorded isolation check](docs/browser-isolation-check.json).

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

JSON output is a report with `query`, `country`, `status`, `results`, `sources`,
`coverage` and `warnings`. Diagnostics stay in JSON for `--json`; text mode sends warnings
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
  adapters/italy/       Demanio, RisorseImmobiliari, Caasa + optional Kyero feeds
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

Public searches are bounded per source:

| Source | Default request budget | Location/search limits |
| --- | --- | --- |
| RisorseImmobiliari | 2 pages/province, 12 details total | Up to 3 nearby provinces; residential catalogue only |
| Caasa | 2 pages/municipality, up to 3 municipalities | Query municipality and immediate neighbours; auctions excluded |
| Demanio | 2 pages/region, 20 details total | Overlapping regions; municipality points only |

Requests identify the app, check robots, wait at least 1 second (2 for Caasa), time
out after 20 seconds, and cap responses at 10 MiB. GET responses have a five-minute
in-process cache. Limits, skipped records and uncertain locations produce partial
coverage diagnostics. No automatic retries or access-control bypasses. The source
reviews document the exact public HTML/helper requests and remaining uncertainties.

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
