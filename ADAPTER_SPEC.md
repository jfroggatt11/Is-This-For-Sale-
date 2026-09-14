# Adapter specification — v0.1

The runtime is deterministic Python. Agents may discover, implement and repair
adapters, but do not run inside searches. A provider must be addable without
editing another provider's extraction code.

## 1. Investigate before implementation

Create `adapter_specs/<source>.md` before writing the adapter. Record the review
date, operator, primary URLs, inventory scope (sales/rentals/auctions), regions
covered, factual observations and remaining uncertainties. Document:

- How listings are exposed: official read API, export feed, structured data,
  sitemap or public HTML. A listing-publication API is not a search API.
- Geographic query behavior: point/radius, polygon, bounding box, municipality,
  or bounded catalogue scan. Inspect the actual public form or published API
  contract. Do not invent endpoint parameters.
- Paging, sorting, response format, normal source empty response, expected
  completeness, likely stability and request budget.
- API/HTML schema, category mapping, price meaning, currency, area units,
  timestamp meaning and coordinate origin/precision.
- Robots URL and observed response, relevant terms/license links, restrictions
  on access, reuse, attribution, caching and fixtures. Distinguish an explicit
  license from an inference that ordinary factual search is permitted.
- Decision: integrate, request legitimate access, investigate further, or reject.

Prefer primary provider documentation and permitted low-volume requests. Public
visibility, robots permission, JSON-LD and a sitemap are not licenses to reuse
the entire site. No login/CAPTCHA bypass, session theft, proxy rotation, invented
API credentials, or third-party scraping services used to evade restrictions.
Do not send permission requests to operators without user authorization.

## 2. Contract

```python
class PropertySourceAdapter(ABC):
    source_name: str
    country_codes: list[str]
    warnings: list[str]

    def search(self, latitude: float, longitude: float, radius_m: float,
               property_types: list[str] | None = None) -> list[Listing]:
        ...
```

Subclass `itsfs.adapters.base.PropertySourceAdapter` and call its constructor.
At the beginning of each search validate with `SearchQuery` **before any I/O**
and reset `warnings`. Inputs are WGS84 degrees and metres. Types are a nonempty
sequence from the shared taxonomy, or None for all supported types. Negative,
zero, NaN/infinite or over-200-km radii are invalid. Raise ValueError for bad input.

Return normalized **candidates**: regional sources may over-select and include
unlocated candidates. `SearchEngine` applies the final type/radius policy. Adapter
callers who need identical filtering should use that engine. Apply safe upstream
filters where supported; do not silently force unsupported ones.

Inject a transport and separate parsing from I/O. Keep parsing independently
callable. Inject a clock when availability depends on time. Adapter instances are
sequential, with no thread-safety guarantee. Avoid shared mutable module state.

## 3. Extraction and normalization

- Every listing needs a stable provider name, provider-scoped ID and useful title.
  Preserve the original detail URL when available; missing optional URLs stay null.
- Admit only positively identified sales. Exclude rentals, awards/sold lots and
  expired offers. Missing availability evidence must be surfaced; it is not an
  active sale. For auctions use the offer deadline and its source time zone.
- Parse locale-specific numbers deterministically. Never convert missing price
  to zero, infer EUR globally, equate rooms with bedrooms, or turn acres into m²
  without a documented conversion. Make asking, auction-base and guide prices
  distinguishable in raw metadata.
- Use the common taxonomy. Map known upstream types explicitly; unknown values
  become `other`. Document category ambiguity and fixtures for each mapping.
- Missing optional fields become None. A malformed optional field may become
  None with a warning. A missing ID/structural marker is not an optional-field case.
- Retain only useful source metadata. Never retain access tokens, cookies, contact
  records, or entire response bodies by default. Source-specific confidential
  notes and images do not belong in normalized runtime output.
- `retrieved_at` is timezone-aware UTC at normalization; in-process cached pages
  can be up to five minutes older. Preserve source update times separately.

## 4. Geography and precision

Coordinates always come as a pair. `exact` requires provider evidence of a property
point. Use `approximate` for generalized property coordinates; `area_only` for
town/area points; `unknown` if no defensible position is available. Never copy the
query centre, agent's office, or nearest city into a purported property point.

The strict engine excludes area-only/unknown records. With `include_unlocated`,
known area points must fall within the numeric radius but remain `unverified`;
the property may lie outside and properties whose town point lies outside may be
missed. Records without coordinates have no computable distance and can represent
only regional candidates. Approximate points have approximate radius matches.
Explain these limits in source notes. No hidden mass geocoding of listing addresses.

## 5. Pagination, errors and load

Use stable upstream paging/order and preserve every filter on each page. Do not
blindly follow next-page links that discard query parameters. Bound pages and
detail requests; stop repeated pages/cursors and preserve duplicate identities.
If a limit prevents full enumeration, append a coverage warning. Never claim
an exhaustive negative answer from a capped or failing source.

Use `PoliteHTTP` for public HTML/feed access. It checks robots (including wildcard
rules), applies crawl delays/request rates, identifies the app, uses HTTPS and
stops on auth denial/429/challenges. Redirects require a reviewed canonical URL;
automatic retries are disabled. Unexpected status/timeout raises `SourceError`.
Forbidden access raises `AccessDenied`; changed root/schema/required labels raise
`SourceChanged`. Do not put URLs containing secrets or raw HTTP bodies in errors.

On individual malformed records, either fail the source or skip with explicit
warnings; do not catch errors and return an unexplained empty list. On 401/403/429,
stop the source immediately. A source-level failure is isolated by the engine.
Generic adapter exception messages are redacted by orchestration.

Request limits are per client/process, not a fleet-wide limiter. A future hosted
deployment must add shared coordination before increasing traffic. No database or
persistent listing cache is part of v0.1.

## 6. Registry

Add metadata to `src/itsfs/data/sources.json` (included in built wheels):

```json
{
  "source": "example", "country_codes": ["IT"],
  "property_types": ["residential", "land", "commercial"],
  "access_method": "public_html", "status": "working", "enabled": true,
  "location_search": true, "location_precision": "approximate",
  "adapter": "example", "options": {},
  "notes": "Describe actual coverage and limits",
  "review": "adapter_specs/example.md (review date)"
}
```

Add the factory to `Registry.load` and the implemented-adapter allowlist in
`SourceSpec`. Imports are explicit Python, never arbitrary import paths supplied
by external JSON. Creation happens per source inside the failure boundary. For a
new dependency, use a lazy import inside its factory if import can fail so other
sources remain usable. Statuses: `working`, `needs_access`, `investigating`,
`unavailable`, `rejected`. Only implemented reviewed working sources are enabled.
`location_search` means native point/radius search or full-feed local filtering;
regional search alone is false. A Kyero agency is a source; the Kyero format itself
is not a public inventory source. Custom config locations resolve relative to the
config file; never commit real bearer URLs.

## 7. Fixtures and conformance

Store minimal fixtures in `tests/fixtures/`, with provenance, license or synthetic
construction notes. Prefer original synthetic records with realistic structure.
Remove personal contacts, cookies, tokens and unnecessary source content. Frozen
time tests must not expire as the calendar advances. Default tests must be offline;
the shared network guard fails unexpected socket access.

Add the implementation to `tests/adapters/test_conformance.py` and extend the
adapter-specific suite. Required cases:

1. Class/registry loading and shared model construction.
2. Valid coordinates, radius and each supported type; invalid input before I/O.
3. Nonempty and genuine empty fixtures, normalized values and complete taxonomy map.
4. Missing optional fields, unknown categories, invalid numbers and coordinates.
5. Multi-page results, filter preservation, duplicates, repeated pages and caps
   where applicable. Full-snapshot feeds document paging as not applicable.
6. Timeout, network errors, access denied and rate-limit handling.
7. Unexpected HTML/JSON/XML, layout/schema changes and dangerous XML where relevant.
8. Source failure isolation, location precision, stale/sold/rental exclusion.
9. Optional live smoke test using an explicit environment switch; an empty result
   is acceptable if the recognized source response is empty. Never require keys
   or network for default CI.

Run `pytest`, `ruff check src tests scripts`, `ruff format --check src tests scripts`
and `python -m build`. Smoke-test the installed wheel so registry/data resources
cannot accidentally work only from the repository. Demonstrate a real location,
label live vs fixture output and disclose all coverage/access limitations.

## 8. Review and maintenance

Keep the PR focused on the source plus its registry entry, review, tests and data
attribution. Human/CI review precedes registry inclusion. When restrictions change
or the source breaks, disable it with the relevant status and explain the evidence.
Do not repair access failures by bypassing the restrictions. Country expansion
also needs locally licensed geography and a documented geocoder strategy.
