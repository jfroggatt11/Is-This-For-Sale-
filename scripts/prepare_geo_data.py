"""Build bundled data from explicitly downloaded primary-source files (no network)."""

import argparse
import hashlib
import json
import unicodedata
import zipfile
from pathlib import Path


def normalize(value):
    return " ".join(
        "".join(
            c
            for c in unicodedata.normalize("NFKD", value.casefold())
            if not unicodedata.combining(c)
        )
        .replace("-", " ")
        .split()
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("cities_zip", type=Path)
    p.add_argument("regions_geojson", type=Path)
    args = p.parse_args()
    target = Path(__file__).resolve().parents[1] / "src/itsfs/data"
    with zipfile.ZipFile(args.cities_zip) as z:
        rows = [r.split("\t") for r in z.read("cities500.txt").decode().splitlines()]
    towns = []
    for r in rows:
        if r[8] != "IT":
            continue
        towns.append(
            dict(
                id=r[0],
                name=r[1],
                names=sorted({normalize(n) for n in [r[1], r[2], *r[3].split(",")] if n}),
                lat=float(r[4]),
                lon=float(r[5]),
                province=r[11],
            )
        )
    (target / "towns.json").write_text(json.dumps(towns, ensure_ascii=False, separators=(",", ":")))
    names = [
        "Piemonte",
        "Valle d'Aosta",
        "Lombardia",
        "Trentino-Alto Adige",
        "Veneto",
        "Friuli Venezia Giulia",
        "Liguria",
        "Emilia-Romagna",
        "Toscana",
        "Umbria",
        "Marche",
        "Lazio",
        "Abruzzo",
        "Molise",
        "Campania",
        "Puglia",
        "Basilicata",
        "Calabria",
        "Sicilia",
        "Sardegna",
    ]
    regions = []

    def points(value):
        if isinstance(value[0], (float, int)):
            yield value
        else:
            for child in value:
                yield from points(child)

    for f in json.loads(args.regions_geojson.read_text())["features"]:
        coords = list(points(f["geometry"]["coordinates"]))
        name = f["properties"]["shapeName"]
        regions.append(
            dict(
                name=name,
                code=f"{names.index(name) + 1:02}",
                geometry=f["geometry"],
                bbox=[
                    min(c[0] for c in coords),
                    min(c[1] for c in coords),
                    max(c[0] for c in coords),
                    max(c[1] for c in coords),
                ],
            )
        )
    assert len(regions) == 20
    (target / "regions.json").write_text(json.dumps(regions, indent=2))
    print(f"Prepared {len(towns)} towns and {len(regions)} regions")
    for path in (args.cities_zip, args.regions_geojson):
        print(path.name, hashlib.sha256(path.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
