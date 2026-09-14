# Italian source investigation

Reviewed 2026-09-14. The goal was initially three useful sources, with no assumption
of programmatic access. **Only one key-free public source was technically
validated and implemented in this phase.** Other candidates stay disabled; the
framework does not pretend that research candidates are working integrations.
No operators were contacted, accounts created, or credentials assumed.

| Source | Exposure / geography | Stability and access | Decision |
| --- | --- | --- | --- |
| Agenzia del Demanio | Public server-rendered sale search; region, province, municipality and use filters; paginated lot details. Address/map query, not property coordinates. | Explicit public sale catalogue, separate authenticated bidding site. Robots returned 404; no public-search prohibition found in inspected legal/footer pages. HTML has no published API stability guarantee. | **Implemented and live-tested**, bounded factual fields only; municipality precision and deadline validation. |
| Idealista | Official Search API is advertised for property integration; detailed access contract requires provider onboarding. | Provider requests a project description before issuing a key. No credentials available. Public API page does not establish unrestricted crawling rights or verified Italian category coverage. | Legitimate future API candidate; **needs access**, not implemented. |
| Immobiliare.it | Official integration documentation describes XML/REST synchronization of an agency's own listings. Separate Insights comparables product requires OAuth. | Agency import API needs credentials/source header and IP coordination. Publishing inventory is not reading the whole portal. | **Needs access** to a suitable read product; no public scraper implemented. |
| Lombardia / Milano public auctions | Open-data catalogue advertises JSON/CSV/GeoJSON for regional public-property auctions, potentially searchable locally by coordinates. Milano derivative explicitly carries CC0. | Metadata points to 2022-era data despite later catalogue updates. Lombardia DNS lookup and Milano download TLS attempts failed in this environment. Actual rows/freshness were not verified. | **Unavailable in this investigation**, worthwhile second public integration only after validating schema, dates and endpoint access. Do not count Milano and Lombardia as independent inventory. |
| Italianhousesforsale | Public category/location HTML including residential, land and commercial categories. | Terms expressly prohibit copying/redistribution/use/publication; robots retrieval also failed during inspection. Structured data does not override those terms. | **Rejected** for this shared search registry without a license. |
| Jaklin Riegelmann | Public category pages; property RSS advertised in external directories. Actual feed endpoint not validated. | Robots permits public pages; terms restrict third-party publication and marketing reuse. | **Rejected** for shared public output; not counted as a compliant feed integration. |
| Nestoria | Historic API references exist. | Current official API/robots pages could not be verified. | Investigating only; no implementation based on historic third-party examples. |
| Invest in Italy Real Estate | Official investment catalogue includes both purchases and long-term leases. | Catalogue purpose verified; direct host/robots access failed. Precise reuse terms and schema unverified. | Investigating; must distinguish sale from concession and proposed development. |
| Owner-supplied Kyero XML | Official full-snapshot specification with sale/rent flag, country, coordinates, categories and URLs. Local radius filtering. | Stable documented format, but source-owner authorization is separate. No feed access presumed. | Optional **format adapter**, not a third public source or a prerequisite. |

## Primary evidence

- [Demanio catalogue](https://venditaimmobili.agenziademanio.it/AsteDemanio/sito.php),
  [search](https://venditaimmobili.agenziademanio.it/AsteDemanio/sito.php/ricerca/),
  [linked agency legal/privacy page](https://www.agenziademanio.it/it/agenzia/privacy/).
  The detailed implementation decision precedes code in
  [adapter_specs/demanio.md](../adapter_specs/demanio.md).
- [Idealista access request](https://developers.idealista.com/access-request).
- [Immobiliare integration documentation](https://feed.immobiliare.it/integration/ii/docs/import/get-start)
  and [Insights comparables](https://insights.immobiliare.it/webdocs/service/comps/getting-started/).
- [Italian national catalogue entry for regional auctions](https://www.dati.gov.it/node/view-dataset/dataset?id=65cd60b5-ac5d-41b4-871c-3d73bae39a11),
  [Milano CC0 dataset](https://dati.comune.milano.it/dataset/ds616_aste_di_vendita_immobili_pubblici_nel_comune_di_milano).
  Dataset identifiers: Lombardia `57ps-t8bu`, Milano regional view `uizd-wnps`,
  Milano local catalogue `DS616`.
- [Italianhousesforsale terms](https://www.italianhousesforsale.com/terms-and-conditions/).
- [Jaklin Riegelmann terms](https://www.jaklin-riegelmann.com/about-us/terms-of-use)
  and [robots](https://www.jaklin-riegelmann.com/robots.txt).
- [Invest in Italy Real Estate purpose](https://www.investinitalyrealestate.com/en/about-us/).
- [Kyero published feed contract](https://help.kyero.com/estate-agents/xml-import-specification)
  and [machine-readable specification](https://feeds.kyero.com/assets/kyero_v3_import_spec.txt).

Network failure is recorded as a technical observation, not proof that a site is
permanently unavailable or that access is forbidden. Robots 404 is not a content
license. The Demanio integration uses small factual extracts and original fixtures;
source descriptions, images, documents and personal contacts are not retained.

## Next useful public-source work

First recheck Lombardia/Milano's openly licensed auction resources and reject
expired offers. Next investigate public land-sale programmes and regional/municipal
sale feeds with explicit reuse terms. Avoid treating property ownership registers,
valuation datasets, proposed disposals, or development concessions as active sales.
Three useful working sources remain a future coverage milestone; this release
delivers the first independently tested and queryable public integration.
