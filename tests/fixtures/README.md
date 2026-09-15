# Fixture provenance

All XML and HTML fixtures in this directory were authored for this repository.
They contain fictitious listings, `example.invalid` URLs and simplified source
structure. No photos, contact details, tender documents, or copied property
descriptions are included. Real Italian place names and geography are used for
distance tests. Test sale deadlines are fixed; parsers receive an injected clock.

The two fictional agency configs in `examples/synthetic-sources.json` share the
Kyero fixture to demonstrate source isolation and conservative URL deduplication.
They are **not two real property providers**. The live Florence result is separately
identified in `docs/DEMO.md`; the default CLI never substitutes fixture listings.

`risorse_search.html`, `risorse_detail.html`, `caasa_city.json` and
`caasa_search.html` are original synthetic structural fixtures based on public
HTML/helper response shapes reviewed on 2026-09-14. IDs, prices, addresses and
properties are fictional. No copied descriptions, photographs or contacts.

`idealista_detail.html` is original synthetic HTML using the factual element
structure observed in a direct browser visit. It is for the no-I/O detail parser;
it is not evidence of a live crawler or a copied real advertisement.
