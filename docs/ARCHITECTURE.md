# Runtime architecture

`SearchQuery` validates coordinates, radius and taxonomy once at the entry point;
each adapter also validates independently before I/O. `SearchEngine` uses explicit
country override or offline Italian polygon containment, then selects enabled
registry sources whose country and type metadata overlap the request.

For each source the engine loads an allowlisted factory inside its failure
boundary, invokes deterministic search, applies common type/radius filtering and
records the source outcome. A programmer error is isolated with a redacted error
message; expected source errors carry safe diagnostics. No third-party adapter
module executes just because an unsupported-country search was requested.

Candidates carry source identity and explicit precision. Exact/approximate points
can be distance-filtered; area-only/unknown candidates are excluded by default.
The opt-in inclusion mode retains honest uncertainty. The engine ranks verified
points before uncertain candidates, then by distance and stable source identity.
Conservative deduplication merges provider IDs or canonical detail URLs and keeps
other source references. It never merges solely on a town point, price or title.

Registry metadata ships as package data. A local JSON configuration can add
separately named authorized Kyero feeds; options containing feed tokens are
excluded from `sources` output. New Python integrations require explicit code
registration, preventing configuration from becoming an arbitrary import mechanism.

`PoliteHTTP` is shared by a registry's adapters: sequential rate limiting, robots
rules, five-minute in-memory page cache, finite response size and timeout. Closing
the registry closes its owned HTTP client. It does not provide persistent storage,
distributed rate limiting or concurrent source execution. A source may return
partial results with warnings; a raised source failure contributes no results.

The `Geocoder` protocol permits future opt-in providers. The implementation in
this release uses only bundled Italian town points. Country boundaries and town
data have distinct roles: an offshore point is never assigned a country merely
because an Italian city is nearby.

Agents belong outside this runtime. Discovery, permission investigation, adapter
maintenance, tests and registry changes happen through repository review. No LLM,
database, web server or hosted service participates in ordinary searches.
