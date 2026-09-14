# Adding a country with a coding agent

Agents work on repository changes, not on each user's search. Unsupported
coordinates currently produce a structured `unsupported` response. No agent is
launched and no paid or external search provider is silently selected.

Example instruction for Codex or Claude Code:

> Investigate the major online property sources used in COUNTRY. Identify sources
> that can be queried in a compliant and technically reasonable way without
> assuming API credentials. Before implementing each source, document its public
> exposure, geographic query, structure, stability and access restrictions in
> adapter_specs/. Add adapters following ADAPTER_SPEC.md, fixtures and tests,
> update the registry, and demonstrate a search around LOCATION. Do not bypass
> access controls. Clearly identify sources requiring authorized access, actual
> live results, fixture demonstrations and unresolved coverage limits.

Expected deliverables:

1. Primary-source access review and explicit go/no-go decisions.
2. Independent deterministic adapters with bounded requests and useful diagnostics.
3. Licensed local country geometry and location lookup, preserving attribution.
   The current detector only knows Italy. Add real polygons, not a country-sized
   rectangle or a nearest-city guess across coastlines/borders.
4. Normalization, availability, location-precision and conformance fixtures.
5. Metadata and factory registration, installed-wheel tests, live demonstration
   where permitted. No placeholders labelled working.
6. Human/CI review, then inclusion in the shared repository registry.

The resulting sequence is: unsupported search → agent investigation → adapter PR
→ conformance tests → human/CI validation → deterministic future searches. A
future maintenance agent can follow the same process after a source layout
changes. Autonomous execution, hosted registries and repair PR automation are
deliberately absent from v0.1.
