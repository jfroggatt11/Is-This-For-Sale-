# Demonstrations

## Combined live Italian search — no credentials

Executed 2026-09-14 through the actual CLI and all three default adapters:

```bash
itsfs search --location "Firenze, FI" --radius 5km --json
```

[Complete real HTTP report](demo-florence-combined-live.json). This is not fixture
output. It returned **45 strict radius matches**, retrieved from 19:00:39 to 19:01:14 UTC:

| Source | Normalized candidates | Results within 5 km |
| --- | ---: | ---: |
| Caasa | 111 | 42 |
| RisorseImmobiliari | 12 | 3 |
| Demanio | 20 | 0 |

All 45 returned matches have approximate property-map locations. Demanio's
municipality-only candidates were excluded by the strict location policy.
Results include residential and commercial property. Price fields are asking
prices for the private-market records. Example factual records include:

| Source | Property | Asking price | Approximate distance |
| --- | --- | ---: | ---: |
| Caasa | Appartamento a Firenze | EUR 595,000 | 219 m |
| RisorseImmobiliari | Terratetto a Firenze | EUR 649,000 | 1,118 m |
| Caasa | Locale commerciale a Firenze | EUR 1,070,000 | 1,250 m |

Every source reported partial coverage because of request budgets or location
limits. A Caasa card whose sale label conflicted with rental text was excluded.
The snapshot preserves the complete per-source diagnostics and timestamps.
Different source URLs may still describe the same property: this count is
returned advertisements, not 45 independently verified unique buildings.

The default search now additionally reports a coverage ledger for all 26
catalogued sources. That field was added after this live snapshot. It records
unqueried source reasons; it does not imply a market-coverage percentage.
The source catalogue and request policies are in [ITALIAN_SOURCES.md](ITALIAN_SOURCES.md).

## Validation after adding the public sources

- 282 offline tests passed; all 3 opt-in live smoke tests passed.
- Caasa's additional live smoke test used Lecco, rather than Florence.
- Ruff lint/format checks passed; source distribution and wheel built successfully.
- Installed wheel checked from `/tmp`: all three factories, 26 registry sources,
  107 province routes, offline geography and coverage reporting load correctly.

## Earlier government-source demonstration

Executed 2026-09-14; the returned listing's normalization timestamp is
`2026-09-14T18:01:09.246796+00:00`. This is a real HTTP search through the package's
public-source adapter, not a browser search or fixture replay.

```bash
itsfs search --location "Firenze, Italy" --radius 10km \
  --type commercial --source demanio --include-unlocated --json
```

The complete report is [demo-florence-live.json](demo-florence-live.json).
It returned this candidate:

| Field | Observed value |
| --- | --- |
| Source / ID | Demanio / 20756 |
| Property | Commercial units, FIB0916, Florence |
| Auction starting price | EUR 2,030,833 |
| Published gross area | 2,142 m² |
| Address | EMPOLI 4 A/B/C, FIRENZE |
| Offer deadline | 28 September 2026, 12:00 Europe/Rome |
| Position | Municipality point, `area_only` |
| Radius verification | `unverified` |

[Original public listing](https://venditaimmobili.agenziademanio.it/AsteDemanio/sito.php/immobile?id-immobile=20756).
The source's starting price and offer deadline are factual observations at the
time of the run; the repository snapshot is not a continuing availability promise.

The result reports **partial** coverage. It reached the page cap and encountered
optional area text it could not interpret on other candidates, retained as null
with warnings. The adapter found two commercial candidates in its bounded regional
scan; only one passed the town-point distance filter. The printed distance is
zero because the search town and listing municipality share the same GeoNames
point. **It is not a property location or an exact distance.** A strict search
without `--include-unlocated` excludes this candidate. No property address was
sent to a geocoding service and no Google map iframe was fetched.

## Offline multi-source conformance example

```bash
itsfs search --location "Anacapri, Italy" --radius 2km \
  --config examples/synthetic-sources.json \
  --source demo_agency_a --source demo_agency_b --json
```

This example deliberately uses fictional Kyero feed listings near a real town.
Two named test sources exercise the same normalization contract, independent
source reports, distance ranking, missing fields and duplicate URL provenance.
The fixture includes residential, land and commercial records, plus rentals and
non-Italian records that must not become sale results. Duplicate homes/land merge
by URL; two unlinked shop records remain separate because identity is uncertain.

There is no automatic fixture fallback in the CLI. Live failures stay visible.

## Major portal attribution probe

The subsequent bounded three-city probe returned 84 approximate radius matches,
with references to 62 distinct Idealista URLs, 64 Immobiliare.it URLs and 54
Wikicasa URLs. None referenced Casa.it. These overlap and are attributed to Caasa,
not independent direct-portal results. See [method, limits and evidence](MAJOR_PORTALS.md).
