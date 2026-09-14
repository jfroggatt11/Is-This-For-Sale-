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
