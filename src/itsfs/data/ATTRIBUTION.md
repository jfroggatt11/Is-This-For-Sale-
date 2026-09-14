# Bundled geographical data

Downloaded 2026-09-14. The MIT code license does not replace these data licenses.

Italy country boundary and regional bounds: geoBoundaries / William & Mary
geoLab, derived from ISTAT (National Institute of Statistics), representing 2023.
The country-specific source license is **CC BY 3.0**; geoBoundaries gbOpen is
distributed with attribution requirements. Preserve this attribution on redistribution.

- https://www.geoboundaries.org/api/current/gbOpen/ITA/ADM0/
- https://www.geoboundaries.org/api/current/gbOpen/ITA/ADM2/
- https://github.com/wmgeolab/geoBoundaries/tree/9469f09/releaseData/gbOpen/ITA
- https://creativecommons.org/licenses/by/3.0/

`italy.geojson` is the unmodified simplified ADM0 download at commit 9469f09.
`regions.json` contains simplified polygons and derived bounding boxes from ADM2 (20 regions;
ADM1 in this dataset means five statistical macroregions). `italy-metadata.json`
records provider metadata. Simplification can miss coastal/border points: country
override is supported. Outside the bundled country, detection returns unknown.

`towns.json`: Italian subset of **GeoNames cities500**, CC BY 4.0. Retains ID,
town names/aliases, WGS84 town point and province code; aliases normalized for
lookup. These are populated-place points, not property coordinates or boundaries.

- https://download.geonames.org/export/dump/cities500.zip
- https://download.geonames.org/export/dump/readme.txt
- https://www.geonames.org/
- https://creativecommons.org/licenses/by/4.0/

Rebuild derived files with `scripts/prepare_geo_data.py CITIES_ZIP REGIONS_GEOJSON`.
No geography downloads occur during ordinary searches. See `docs/GEO_DATA.md` for
the input checksums of this release.
