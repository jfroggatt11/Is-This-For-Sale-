# Idealista website adapter — 2026-09-15

## Scope and project instruction

The owner explicitly revised the original brief on 2026-09-15: reproducibility
is required and website terms are no longer a project constraint. This is not
operator consent. Live robots checks, bounded requests and no CAPTCHA or
access-control bypass remain in force. No account, API key or operator enquiry
is required by the implemented browser path; no enquiry has been sent.

## Evidence

Normal connected Chrome navigation reached:

- https://www.idealista.it/vendita-case/firenze-firenze/
- https://www.idealista.it/vendita-case/firenze-firenze/con-aste_no/
- https://www.idealista.it/immobile/35691213/

The homepage's automatic device check completed without intervention. Optional
cookies were declined and no login occurred. The Florence municipality link and
the **Escludi aste** control were inspected and exercised. Actual keyboard events
also produced municipality autocomplete links, labelled `Comune`, distinct from
province, zone and district suggestions.

Listing 35691213 displayed an asking price of EUR 299,000, 78 m² commercial area,
70 m² usable area, three rooms and two bathrooms, at Via Niccolo' Piccinni 42,
Castello, Firenze. This proves displayed facts, not seller-confirmed availability.
[Timestamped direct-page observation](../docs/idealista-website-live.json).

A separate standalone CLI attempt using fresh, headed Playwright Chrome returned
**HTTP 403** at the homepage and stopped. Therefore reachability of the normal
Chrome session does not prove the Playwright transport works. That shared-profile route is now retired: the owner subsequently required a
fresh browser separate from personal Chrome.

The subsequent CLI test using the separately installed Chromium / Chrome for Testing
and a newly created temporary profile also returned **HTTP 403** and stopped.
[Fresh-browser live result](../docs/idealista-isolated-live.json). Isolation is
verified; successful direct extraction in this fresh environment remains unresolved.

A follow-up passive device-check diagnostic established that the 403 homepage
contains a DataDome interstitial, which did not finish within 30 seconds. Opening
the already observed Florence sale URL directly in a new temporary profile led to
an **interactive visual/audio CAPTCHA**, with no listing content. No challenge was
used, no identity was changed, and no request was retried.
[Sanitized diagnostics](../docs/idealista-device-check-live.json).

The iframe navigated from `/interstitial/` to `/captcha/` without changing its HTML
`src` attribute. Detection now checks the actual frame navigation URL as well as
DOM markers. The adapter permits a bounded passive automatic check on an explicit
device-check interstitial, while stopping on interactive challenges and ordinary
401/403/429 denials. Fresh-browser extraction remains blocked by the access gate;
this diagnostic does not demonstrate a working Idealista search adapter.

## Runtime

`IdealistaAdapter.search(latitude, longitude, radius_m, property_types)` uses the
nearest bundled town to resolve a municipality through observed homepage links
or the site's normal autocomplete UI. It follows the residential sale route,
selects auction exclusion, and captures at most 30 factual cards from the first
page. The Python parser and engine handle normalization, source outcomes,
deduplication and final geographic filtering. No LLM runs at search time.

The only supported browser backend now launches Playwright's separately installed
Chromium / Chrome for Testing. Every search creates a new temporary user-data
directory, starts its own browser process and empty context, then closes the context
and removes the directory. The runtime accepts no personal profile path, saved
storage, browser channel, executable override or remote-debugging endpoint. It
never attaches to the connected personal Chrome browser or falls back to it.

The former extension bridge is removed from the Python package and rejected by
the CLI. Its connection page is retired. An extension previously loaded in personal
Chrome is no longer used. No personal browser settings are changed by this revision.

`python scripts/check_browser_isolation.py` exercises two actual fresh browser runs
against intercepted synthetic pages, verifying empty storage on entry, distinct
profile directories and cleanup after exit. The normal unit suite covers cleanup
on source and launch errors, default routing, and rejection of the old backend.
[Recorded isolation evidence](../docs/browser-isolation-check.json).

Robots checks and at least two seconds between top-level navigations remain.
There are no stealth, cookie import, proxy-rotation or challenge-solver options.

## Observed DOM contract

- Search header: `#h1-container`; sale tab: `#tab-buy[aria-selected=true]`.
- Auction dropdown placeholder must be `Escludi aste`, and the canonical route
  must end `/con-aste_no/`.
- Cards: `article.item[data-element-id]`, link `a.item-link` with an exactly
  matching `/immobile/<numeric ID>/` href. These are heading-role anchors, not h2.
- Asking price: `.item-price`, not the previous price. Area and total rooms:
  `.item-detail`. Rooms are not bedrooms. Unknown optional numbers remain null.
- The separate detail parser reads `h1 .main-info__title-main`, the total-price
  row explicitly labelled `Prezzo dell'immobile:`, feature lists and the observed
  five-line `#headerMap` location layout. It requires an explicit capture timestamp.

Descriptions, photos, contacts and browser state are excluded from captured facts
and normalized output. Synthetic test fixtures are original examples, not copies
of advertisements. Browser captures retain their actual timestamp during parsing.

## Limits

Only reviewed residential title families are accepted. No land or commercial
coverage is claimed for this adapter. One municipality/first page cannot establish
countrywide recall, and nearest populated-place routing can fail or miss adjacent
municipalities. Unsupported title families are skipped with warnings.

Property coordinates were not established. Unambiguous town labels may use bundled
centroids, explicitly `area_only`; otherwise coordinates remain unknown. Strict
radius searches exclude both. `--include-unlocated` exposes uncertain candidates
with `radius_match: unverified` and must not be described as property-distance proof.

[Robots](https://www.idealista.it/robots.txt) disallows `/*/lista-*.htm`; no pagination
is fetched. The site controls its own UI/resource requests. [Italian terms](https://www.idealista.it/assistenzautenti/articoli/condizioni-generali-del-servizio/)
restrict automated extraction without consent; the owner's waiver changes the
project brief, not the site's stated position.
