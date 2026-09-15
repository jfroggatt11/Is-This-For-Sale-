# Major Italian portals: access and measured attribution

Reviewed 2026-09-14. The current credential-free route is bounded Caasa search.
It returns normalized property facts plus publisher references from Caasa's public
cards. A reference does not establish that we fetched that portal or that its
advertisement is still available. Direct coverage of the four portals below
remains unfinished; this is not a claim of countrywide completeness.

## Direct routes investigated

The [2026-09-15 browser test](../adapter_specs/idealista.md) now proves direct
Idealista website retrieval works in connected Chrome. Normal navigation reached
Florence sale results and listing 35691213 (EUR 299,000, 78 m²). The device check
completed automatically. [Normalized direct-source evidence](idealista-website-live.json)
is separate from the earlier Caasa references. A no-I/O detail parser is implemented;
an experimental common-interface browser adapter is implemented.
The owner waived the original site-terms constraint on 2026-09-15. A fresh
Playwright Chrome session returned 403. The owner now requires a fresh browser;
the runtime uses separately installed Chromium and a new temporary profile for
every search. The shared-profile companion is retired.
[Installation and reproducible command](../README.md#direct-idealista-browser-search-experimental).

| Portal | Primary evidence | Current decision |
| --- | --- | --- |
| Idealista | [Official Search API application](https://developers.idealista.com/access-request) asks for name, email and project description before an API key. [Italian terms](https://www.idealista.it/assistenzautenti/articoli/condizioni-generali-del-servizio/), updated 27 May 2026, restrict automated extraction and linking without written consent. Anonymous homepage returned 403. | Normal Chrome website retrieval verified; experimental fresh-browser adapter implemented. Earlier Playwright Chrome session denied (403); personal-profile access is not used by the runtime. |
| Immobiliare.it | [Insights Comps documentation](https://insights.immobiliare.it/webdocs/service/comps/getting-started/) supports paginated comparable search, including bounding boxes, and requires OAuth. [Import documentation](https://feed.immobiliare.it/integration/ii/docs/import/get-start) describes publishing agency inventory. Anonymous homepage returned 403. | A documented read product exists, but access, current-listing semantics and redistribution rights require an agreement. The publishing API cannot retrieve the portal inventory. |
| Wikicasa | [Wikicasa Dati](https://www.wikicasa.it/dati) offers listing data from Wikicasa and Commerciali.it by enquiry. Its inventory product is shown as spreadsheet delivery; the explicitly advertised API concerns the IAREE valuation product. Anonymous homepage returned 403. | Investigate an inventory data-supply agreement. A valuation API is not proof of a public listing-search API. |
| Casa.it | Anonymous homepage returned 403; reviewed robots restrict search routes. This investigation did not establish an official credential-free read API or a usable data-supply contract. | Direct access unresolved. Search-engine indexing and third-party scraper products do not establish an authorized runtime integration. |

No accounts, contact forms or applications have been submitted. No fees or
contracts have been accepted. These are findings about the available routes,
not a demand that the project owner already possess API credentials. A source
operator's decision cannot be obtained by implementing an adapter stub.

## What the implementation now exposes

Every result can include `publisher_references` containing `publisher`, `url`,
`observed_via` and `verification: not_fetched`. Caasa remains `source: caasa`.
The CLI prints origin references; JSON includes per-publisher hit and distinct-URL
counts under `coverage.publisher_references`. Counts cover only returned radius
matches, overlap between publishers, and must not be summed as unique properties.
The direct-source coverage ledger still reports the portals as disabled.

The parser reads actual HTML href destinations associated with the same Caasa
advertisement ID. It combines promoted and regular cards and repeated pages,
removes tracking parameters and does not fetch any destination or ClickTag route.
It omits unreviewed query-based URL identities. Hostnames, not Caasa's display
labels, determine publisher identity. Attribution is an assertion by Caasa;
it does not independently prove that two differently identified records are the
same property. Reference URLs therefore do not change cross-source deduplication.

Use the normal search:

```bash
itsfs search --location "Firenze, FI" --radius 5km --source caasa --json
```

Or reproduce the smaller measurement (one municipality and two pages per city):

```bash
python scripts/probe_publishers.py > docs/publisher-probe-live.json
```

The probe stores timestamps, query parameters, per-result provenance and an HTTP
request ledger. It stops after a source error. There is no known total inventory
denominator, so it cannot estimate recall or national coverage. Zero observed
references means only that this bounded sample did not expose that publisher.

## Live measurement

[Machine-readable evidence and request ledger](publisher-probe-live.json),
2026-09-14 20:06:20–20:07:34 UTC. Residential sale searches; 5 km radius around
bundled town points; two pages from one municipality per city. All 84 returned
matches use approximate property coordinates. 108 normalized candidates were
inspected; the engine excluded 24 outside the radius. The source parser also
excluded one conflicting sale/rental advertisement in Florence.

| Search | Radius matches | With Idealista reference | With Immobiliare.it reference | With Wikicasa reference | With Casa.it reference |
| --- | ---: | ---: | ---: | ---: | ---: |
| Florence | 36 | 27 | 23 | 23 | 0 |
| Milan | 34 | 24 | 29 | 21 | 0 |
| Rome | 14 | 11 | 12 | 10 | 0 |
| Total | 84 | 62 | 64 | 54 | 0 |

Distinct origin URL totals were also 62, 64 and 54 respectively. These columns
**overlap**: a single Caasa record can cite multiple portals. This sample does not
measure how many listings those portals contain or how many Caasa misses. Rome's
municipality search includes properties beyond 5 km; the low retained count is
not evidence of a small Rome market. Casa.it remains an explicit unmeasured gap.
The ledger records 13 requests, all to `www.caasa.it`, including robots, three
location lookups, three search-URL resolutions and six result pages.

Validation: 298 offline tests passed; Ruff passed; the three-city live probe
completed with expected pagination/municipality-limit warnings. Wheel and source
distribution build successfully. The probe is evidence of a dated observation,
not a guarantee that the URLs remain live.

## Prepared access enquiry text

Draft only; not submitted. The Idealista form needs an actual applicant name and
email. For Immobiliare.it and Wikicasa, use their operator's enquiry process to
confirm the appropriate product before developing against it.

> We are developing Is This For Sale, an open-source Python library and CLI for
> point-and-radius property searches, initially in Italy. Searches run on demand
> through deterministic source adapters. We would like to understand whether you
> offer approved read access to current for-sale inventory for this use, including
> residential, land and commercial listings. We need listing ID, original URL,
> asking price/currency, type, area, location precision, coordinates where allowed,
> and current availability. We do not require photos, descriptions or contact data.
> Please confirm Italian coverage, geographic and pagination limits, quotas and
> pricing, attribution/linking requirements, permitted local output and caching,
> removal obligations, and whether an open-source client may be distributed with
> each user supplying their own credentials. Is a free development tier, research
> arrangement or limited pilot available? We would need explicit permission before
> enabling hosted redistribution or publishing inventory datasets.

For Idealista, submit this as the project description in the official Search API
application. For Immobiliare.it, ask whether Insights Offerta comparables include
currently active sale listings with usable original URLs and permitted search
output. For Wikicasa, ask whether listing-data delivery supports incremental
updates or a read API separately from valuation. For Casa.it, a suitable official
inventory-read route remains to be identified; do not assume that any advertised
third-party API is operated or licensed by Casa.it.
