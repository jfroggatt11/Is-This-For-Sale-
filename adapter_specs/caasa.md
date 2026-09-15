# Caasa — reviewed 2026-09-14

Operator: Plus Immobiliare sas. National aggregator of partner property portals.
Decision: integrate bounded public factual search; no account, paid API, dataset,
CAPTCHA bypass, click-tracking requests or downstream portal fetching.

## Primary sources and access assessment

- https://www.caasa.it/robots.txt permits public results and location helpers,
  explicitly describes crawler rate limits; disallows /ClickTag*, /report*,
  /profile*, /docs/, /admin/, /errors/, /clicks.jsp, /similars.jsp, /keep-alive.jsp.
  Use a two-second minimum interval and runtime robots checks.
- https://blog.caasa.it/tutto-su-caasa/ explains aggregation and provenance.
- https://blog.caasa.it/tutto-su-caasa/privacy/ describes its access and data policy.
- https://blog.caasa.it/servizi/dati-strumenti-analisi-mercato-immobiliare/ offers
  licensed bulk data and QIC API access separately, on request. These are NOT used.
- https://www.caasa.it/toscana/cerco-case-in-vendita.html and its public browser
  script https://cdn.caasa.it/static/js/script.3b.min.js?v=3b.4a define the lookup
  and search schema below. Do not access account/Firebase or valuation features.

No open license to republish the whole listing database was found. This review
supports bounded local factual lookup with attribution and links, not bulk reuse.
No source descriptions, photos, agency contacts or complete bodies are persisted
by the runtime. Caasa is the source of these results; its downstream publishers
are not counted as additional implemented adapters. Reassess before hosted reuse.

## Observed public search contract

The public current-location button calls GET `/city.jsp?lat=...&lng=...`.
Response: region slug, province code, city id/name, center, bounds, neighbours.
Public JS's read-only URL resolver POST `/explain.jsp` accepts form fields
`advtype=S`, `searchobject=<JSON>`, returning `{canonical,title}`. That operation
only describes a search; saving a search is a separate authenticated operation
and is never invoked. JSON has location {region,province,cities:[{id,name,zones:[],
hasBigZones}]}, keywords {homeType,options:[],condition:[]}, price/mq {smin:0,smax:0},
`legal=e` (exclude auctions), `efficencyClass=G`. Names match source spelling.
Follow only validated same-origin sale canonical paths and next-page links that
preserve query filters. Page order defaults to relevance, 18 cards/page on review.

Coordinate search selects the containing/nearest municipality. The adapter also
considers the supplied immediate neighbours whose bounding boxes intersect the
radius, max 3 municipalities. It does not expand recursively: large radii and
boundary/sparse data can miss municipalities. Max 2 result pages per municipality;
all caps reported. Radius matching is applied by the common engine.

## Extraction

Parse JSON-LD WebPageElement with `about` property, `offers` and a numeric
`about.identifier`. Match only offers positively labeled `in vendita`, excluding
unavailable/SoldOut/Discontinued and auctions. Property URL is Caasa's permanent
`vendita-<hex>-opinione.html`, never a click tracker. Filtered searches omit most JSON-LD; use the equivalent public `.result-item`
HTML facts (data-id, sale marker, canonical URL, factual image alt, price/surface
and map link). `#titlesection` with a sale heading identifies results; a zero
intro count plus `Nessun risultato trovato.` identifies a genuine empty page. Missing/malformed
root data fails; bad records warn. Repeated IDs/pages stop pagination.

Only numeric price with explicit currency, m² floorSize with MTK unit, property
address and geo are retained. The title is generated from the factual offer type
and municipality. Never use the seller address or city market-statistics point.
Property map coordinates are approximate; a point identical to the source's town
center is area_only. Missing coordinates fall back to municipality/unknown.
Advertisements can be stale: public sale status is evidence of an advertisement,
not a guarantee of availability. Source snippets that conflict with sale status
are excluded when the visible card explicitly proposes a rental.

Explicit Italian type mapping covers residential, commercial, agricultural, land,
industrial and development. Ambiguous/unknown becomes other. Exclude auction
inventory upstream so bidding/deadline semantics cannot masquerade as asking price.
Synthetic fixtures only; opt-in live tests and combined demo required.

## Publisher attribution extension — 2026-09-14

Public cards contain `/ClickTag?url=<destination>&adv=<Caasa ID>&agency=<label>`
anchors. Read these href strings from the already retrieved result HTML; **never
request** the robots-blocked tracker or destination. Retain only references whose
`adv` matches the surrounding card's `data-id`. Derive the publisher from the
actual destination hostname, not the `agency` label (e.g. `wikicasa.free` points
to wikicasa.it). Union promoted/regular cards and repeated pages with the same ID.
Reject credentials, ports, non-HTTP(S), malformed URLs, empty paths and functional
query parameters; omit tracking queries and fragments. Query-identified listings
are omitted until their URL contract is reviewed. References are attributed to
Caasa and explicitly `not_fetched`; they are not independently verified origin
listings, direct integrations, or evidence of current availability. They do not
change identity matching between distinct Caasa listings. A missing reference
means unobserved in the bounded results, not absence from that publisher.

Shared JSON `publisher_references` and `coverage.publisher_references` expose
attribution and counts within returned radius matches. Counts overlap. They are
not percentages of a publisher's inventory. Reproduce the limited three-city
observation with `python scripts/probe_publishers.py`; the probe records a request
ledger and stops after a source error. This is local source provenance, not a
license to republish downstream portal content or create a competing database.
