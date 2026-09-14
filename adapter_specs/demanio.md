# Agenzia del Demanio — public sale catalogue

Investigation: 2026-09-14, before implementation. Decision: implement a bounded,
read-only HTML adapter. No API key, account, browser automation, or LLM required.

## Exposure and access

- Source: https://venditaimmobili.agenziademanio.it/AsteDemanio/sito.php
- Public GET search form: `/AsteDemanio/sito.php/ricerca/`.
- Property pages: `/AsteDemanio/sito.php/immobile?id-immobile=…`.
- The homepage explicitly presents state property offered for sale and separates
  rentals/concessions. Bidding links lead to a separate authenticated platform;
  this integration never follows them or downloads tender documents.
- On review, `/robots.txt` returned HTTP 404. Runtime checks it on each client
  session; denial, auth challenges, 429, and policy retrieval failures stop access.
- Reviewed the homepage, footer, Documenti page, and the agency's linked legal
  notice at https://www.agenziademanio.it/it/agenzia/privacy/ . No prohibition on
  ordinary public search/factual extraction was found in those pages. This is a
  limited access assessment, not a claim that the entire catalogue is open-licensed.
  Retain only factual fields and links; do not republish descriptions, photographs,
  personal contact details, PDFs, or cadastral documents. Fixtures are synthetic.
- Use an identifying `IsThisForSale/0.1` user agent, >=1 second between requests,
  bounded pages/details, no automatic retries and no access-control workarounds.

## Search and geography

The actual form exposes `f_ricerca=vendite`, `f_regione` (two-digit ISTAT region),
`f_provincia`, `f_comune`, `f_destinazione`, `f_datada` (DD/MM/YYYY, examination
date), `f_aggiudicati=-1` (not awarded), and `f_np` (one-based page). Region values
were inspected in HTML; no private endpoint is used. Pagination links show ten
properties per page. Restrict to regions whose offline bounding boxes intersect
the search circle's bounding box, then filter results by distance locally.

The inspected Florence lot (20756) publishes an address in the map iframe,
**not latitude/longitude**. Do not call Google or invent a rooftop point. Resolve
the municipality through bundled GeoNames town points, mark `area_only`, and
require `--include-unlocated` to include those uncertain candidates. Distance is
to the town point, not the property. Missing/ambiguous municipality stays unknown.
Region bounding boxes deliberately over-select; they cannot prove a radius match.

## Extraction and status

Use labelled table rows (`Lotto`, `Prezzo Base`, `Scadenza Offerte`, `Tipologia`,
`Destinazione`, `Superficie Lorda`) and address list items (`Comune`, `Via`).
Italian numbers use dots for thousands and commas for decimals. Bedrooms are
absent; never interpret `Vani` as bedrooms. `Terreni` maps to land, except an
explicit agricultural designation maps to agricultural. Residential and
commercial/office uses map to the shared taxonomy. Unknowns remain `other`.

Prices are auction starting prices, explicitly identified in raw metadata.
Exclude awarded lots and passed offer deadlines in Europe/Rome. A missing or
malformed deadline is not evidence of availability: skip with a warning. Date-only
deadlines are treated conservatively as the start of that local day.

## Stability and limits

Moderate/low: ordinary server-rendered HTML, stable labelled fields, no published
API contract. Require recognizable search form/count and detail labels; detect
unexpected layouts instead of returning a misleading empty success. Search is
bounded (default 2 pages per region and 20 detail requests total), with explicit
partial-coverage warnings. Cache fetched pages in-process for five minutes.
Only the centre country's adapters run; this is not a cross-border search engine.
