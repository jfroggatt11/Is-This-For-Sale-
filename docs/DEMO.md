# Demonstrations

## Live Italian search — no key or login

Executed 2026-09-14; the returned listing's normalization timestamp is
`2026-09-14T18:01:09.246796+00:00`. This is a real HTTP search through the package's
public-source adapter, not a browser search or fixture replay.

```bash
itsfs search --location "Firenze, Italy" --radius 10km \
  --type commercial --include-unlocated --json
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
