# Italian source coverage and access investigation

Reviewed 2026-09-14. **Three credential-free sources are implemented and live-tested:
Demanio, RisorseImmobiliari and Caasa.** The registry records 26 candidate sources,
including usable sources, access restrictions and unfinished investigations. The
catalogue is a growing inventory, not a claim that every Italian source has been
found. No accounts were created and no operators were contacted.

## Working integrations

| Source | Inventory and geography | Actual integration and limits |
| --- | --- | --- |
| [RisorseImmobiliari](https://www.risorseimmobiliari.it/) | National agency portal; residential sales including garages | 107 observed province routes, nearby-town routing, 2 pages/province and 12 detail requests total. Property map points where supplied, otherwise municipality/unknown. Residential catalogue only so far. [Access/schema review](../adapter_specs/risorseimmobiliari.md). |
| [Caasa](https://www.caasa.it/) | National aggregator of portal listings; residential, commercial, agricultural, land, industrial and development | Public location lookup and search resolver, up to 3 municipalities and 2 result pages each. Auctions excluded; facts from public cards/JSON-LD. No paid API or downstream portal requests. [Access/schema review](../adapter_specs/caasa.md). |
| [Demanio](https://venditaimmobili.agenziademanio.it/AsteDemanio/sito.php) | State-property sales and auctions | 2 pages/region, 20 detail requests, deadline/award checks; municipality-level location only. [Access/schema review](../adapter_specs/demanio.md). |

The combined Florence demonstration produced **45 strict radius results** from
both private-market sources. See [DEMO.md](DEMO.md). Caasa's partner portals are
**not** counted as independently integrated sources. They may overlap with each
other and with direct adapters. Cross-source property identity remains uncertain
when distinct URLs advertise the same home.

No blanket open inventory license was found for the working HTML sources. The
implementation performs bounded local factual lookup, retains attribution and
links, and omits descriptions, photos, contacts and source bodies. This does not
license bulk replication or hosted republication. Runtime robots checks and
source failures remain binding. Source snapshots are not ongoing availability
assurances.

## Major portal follow-up

[Access investigation and publisher measurement](MAJOR_PORTALS.md) records the
Idealista application, Immobiliare.it read API and Wikicasa data-supply route.
Publisher references now appear in Caasa results and are counted separately from
direct integrations. Wikicasa is now `needs_access` for its data-supply product;
the earlier homepage probe below still describes its HTML access.

## Investigated sources and remaining gaps

| Candidate | Observed evidence | Registry decision / next step |
| --- | --- | --- |
| Idealista | [Browser investigation](../adapter_specs/idealista.md): normal Chrome pages accessible, fresh Playwright session returned 403 | `experimental`, fresh bundled Chromium per search. First-page residential sales, area-only location. Shared-profile companion retired. |
| Immobiliare.it | [Import docs](https://feed.immobiliare.it/integration/ii/docs/import/get-start) describe publishing agency inventory; [Insights](https://insights.immobiliare.it/webdocs/service/comps/getting-started/) requires authorization; homepage returned 403 | `needs_access` to a suitable read product. An upload API is not a portal-search API. |
| PCase | Public search pages available; [terms modal](https://www.pcase.it/ajax/modal_privacy/) discusses authorized partner exports and unauthorized crawler extraction | `needs_access` for this aggregation use. Do not use robots-blocked RSS or `/include/` endpoints. |
| CasaDaPrivato | [Terms 2.13](https://www.casadaprivato.it/info/policies/regolamento) restrict reproduction/distribution; partner export arrangements described separately | `needs_access`; attractive independent private-owner inventory. |
| TrovaCasa | [General conditions](https://www.trovacasa.it/info/condizioni-generali) restrict reproduction/distribution without authorization | `needs_access`; public reachability alone does not establish permitted reuse. |
| Tecnocasa | [Usage policy](https://www.tecnocasa.it/privacy/policy-utilizzo.html) restricts professional reuse and deep links | `needs_access` for shared aggregation. |
| Wikicasa | [Robots](https://www.wikicasa.it/robots.txt) readable, homepage returned 403 | `unavailable` in this investigation; access stopped. |
| Casa.it | [Robots](https://www.casa.it/robots.txt) limits search paths; homepage returned 403 | `unavailable`; no alternate search API attempted. |
| Gate-away | Homepage returned an anti-bot interstitial instead of property content | `unavailable`; no challenge bypass. |
| Case24 | Robots readable but homepage timed out twice; `/immobili.php` search handler disallowed | `unavailable`; review public SEO paths and terms when reachable. |
| BachecaCase | Homepage accessible. Robots restrict `/immobile/` and `/view-immobile/`; separate `/scheda-immobile/` links exist | `investigating`; full path/terms/schema review needed. |
| Casando | [Public catalogue](https://www.casando.it/immobili.php?city_id=0&p=1) and one property page validated; [privacy](https://www.casando.it/privacy.php) reviewed; robots 404 | `investigating`; direct agency network in Lombardy/Piedmont. Implement sale/rental/sold checks and location provenance next. Not counted as working yet. |
| Immobiliare Italia | La Spezia/Massa Carrara agency; [terms 4](https://www.immobiliareitalia.it/termini-e-condizioni/) limit reproduction/commercial reuse | `needs_access`; personal downloads do not authorize shared republication. |
| Quimmo | Homepage/robots accessible; both private sales and auctions | `investigating`; [terms](https://aiuto.quimmo.it/termini-e-condizioni), search and deadline/price semantics still need review. |
| AsteAnnunci | Robots returned 403 | `unavailable`; listing requests not made. |
| ImmobiliAllAsta | Robots returned 530 | `unavailable`; access policy could not be checked. |
| Romolini | Robots readable; query filters restricted; language redirects need canonical-host review | `investigating`; no listing collection. |
| CasaSpeciale | Regional candidate; robots redirected | `investigating`; establish canonical host and review [conditions](https://www.casaspeciale.it/tuttosucasaspeciale/condizionidiutilizzo/). |
| Lombardia / Milano public auctions | [Regional metadata](https://www.dati.gov.it/node/view-dataset/dataset?id=65cd60b5-ac5d-41b4-871c-3d73bae39a11), [Milano CC0 derivative](https://dati.comune.milano.it/dataset/ds616_aste_di_vendita_immobili_pubblici_nel_comune_di_milano) | `unavailable`; endpoint DNS/TLS failed and metadata suggests old inventory. Verify freshness before integration; do not count the derivative twice. |
| Italianhousesforsale | [Terms](https://www.italianhousesforsale.com/terms-and-conditions/) prohibit copying/reuse/publication | `rejected` without a license. |
| Jaklin Riegelmann | [Terms](https://www.jaklin-riegelmann.com/about-us/terms-of-use) restrict third-party publication/marketing reuse | `rejected` for shared output without a license. |
| Nestoria | Historical API references, current official contract not verified | `investigating`; no adapter based on obsolete examples. |
| Invest in Italy Real Estate | Investment catalogue mixes purchases, concessions and leases; direct connection failed | `unavailable`; confirm current schema, sale status and reuse. |

A network error describes this investigation, not permanent unavailability.
Disabled entries' broad taxonomy fields are discovery scope, not verified category
coverage. `itsfs sources --json` exposes implementation/access states; search JSON
also includes sources not searched and the reason. A catalogue count is not a
percentage of the Italian market.

## Expanding toward country coverage

Continue discovering sources across national portals, agency networks, independent
agency sites, private-owner portals, specialist land/commercial sites, auctions,
banks and municipal disposals. Add each candidate with primary evidence and a
clear decision. Prioritize independent inventory and precise geographic search,
not nominal source counts or multiple views of the same feed.

The next direct-source candidate is Casando. BachecaCase and Quimmo need more
investigation. Broaden RisorseImmobiliari beyond its residential catalogue, then
improve municipality coverage and entity resolution using publisher-provided
identities. Restricted national portals need legitimate access arrangements;
those are separate work, not prerequisites for running the current MVP.

The optional [Kyero feed adapter](../adapter_specs/kyero_feed.md) supports an
owner-authorized export when one exists. It is neither assumed nor counted as
public inventory. The runtime never discovers credentials or contacts operators.
