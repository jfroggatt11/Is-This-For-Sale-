# Geographic data reproducibility

The bundled country polygon supports Italy, Sicily, Sardinia and represented
small islands, with enclave holes. Tests include Anacapri, Corsica, San Marino and
Vatican City. Simplified boundaries are unsuitable for parcel decisions and can
misclassify a point very near a coast/border. Other countries currently return
unknown unless explicitly supplied. `--country` is a routing override, not a claim
of authoritative boundary accuracy.

The regional dataset contains simplified polygons and their bounding boxes.
Bounding-box intersection conservatively selects possible regions; actual polygon
containment puts the centre region first. This reduces request waste but is not
an exact circle/polygon intersection. Listing filtering uses haversine distances.

Inputs downloaded on 2026-09-14:

| Input | SHA-256 |
| --- | --- |
| GeoNames cities500.zip | `51e6a12a36eb8bfba9005dd2cc4a79002092d2e2074de8bd53edb7424bc70181` |
| geoBoundaries ITA ADM2 simplified, commit 9469f09 | `a01b6408d7d9061318034f8f4f54b377b99b5f8dcf5a7f84c5fa1e8ee3c86549` |

The source URLs and licenses are in
[ATTRIBUTION.md](../src/itsfs/data/ATTRIBUTION.md). The current GeoNames zip URL is
mutable; preserve these hashes with releases. `scripts/prepare_geo_data.py`
extracts only Italian populated places, normalizes names/aliases and preserves
province codes. It validates that the region input contains 20 mapped regions.

```bash
python scripts/prepare_geo_data.py /path/to/cities500.zip /path/to/ITA-ADM2.geojson
```

No network access occurs in this build script or ordinary geocoding/country
detection. A `Geocoder` protocol allows a separately reviewed provider to be added
later. This release intentionally performs no remote per-listing address geocoding.
