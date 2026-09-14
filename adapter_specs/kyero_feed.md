# Optional Kyero-format agency feed

Investigation: 2026-09-14. This is a format adapter, **not access to Kyero's portal
inventory**, and is not counted as a freely available Italian listing source.
It is supplementary; the default source requires no credentials.

Primary contract: https://help.kyero.com/estate-agents/xml-import-specification
and https://feeds.kyero.com/assets/kyero_v3_import_spec.txt (retrieved successfully).
The provider publishes a version 3 full-snapshot XML format with IDs, price_freq,
country, category, location, surface_area and language-specific URLs.

Access: only a local owner-supplied export or a feed whose owner authorizes this
use. A discoverable feed URL alone is not permission. Configure named agency
sources separately with an access review. HTTPS fetches check robots, do not
follow redirects, and stop on 401/403/429; no credential guessing or feed discovery.

No remote geographic query or pagination: fetch one bounded full snapshot, then
filter locally. Only `price_freq=sale` and country Italy/Italia/IT are admitted;
missing country defaults to Spain in the upstream spec and must not become Italy.
Coordinates are approximate unless a future source-specific review proves exact.
Missing or zero coordinates are unknown. The feed format's zero beds/areas mean
unknown. Use plot area for land/agricultural/development, built area for buildings.
Missing listing URLs remain null. Partial ownership/leasehold remain visible in
raw metadata. Reject unsafe XML and unexpected roots/versions; warn on skipped
malformed records. No images, contact data or free-text notes are retained.

Stability: good format documentation; actual feed freshness is the owner's
responsibility. Parser tests use original synthetic fixtures, not portal copies.
