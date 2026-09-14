import json
from dataclasses import replace

import pytest

from itsfs.adapters.base import SourceError
from itsfs.cli import main
from itsfs.models import Listing, SearchQuery
from itsfs.registry import Registry, SourceSpec
from itsfs.search import SearchEngine


def spec(source="test"):
    return SourceSpec(
        source,
        ["IT"],
        ["residential", "land"],
        "test",
        "working",
        True,
        "approximate",
        "kyero",
        True,
        review="synthetic test",
    )


class Adapter:
    warnings = []

    def __init__(self, result):
        self.result = result

    def search(self, *args):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def test_failure_isolation_filtering_ranking():
    r = Registry([spec("bad"), spec("good")])
    listing = Listing(
        "good",
        "1",
        "Home",
        latitude=40.553,
        longitude=14.218,
        location_precision="approximate",
        property_type="residential",
    )
    r.instances = {
        "bad": Adapter(SourceError("unavailable")),
        "good": Adapter(
            [
                replace(listing, source_id="far", latitude=45),
                listing,
                replace(
                    listing,
                    source_id="unknown",
                    latitude=None,
                    longitude=None,
                    location_precision="unknown",
                ),
            ]
        ),
    }
    report = SearchEngine(r).search(SearchQuery(40.553, 14.218, 1000))
    assert report.status == "partial"
    assert [x.listing.source_id for x in report.results] == ["1"]
    assert report.sources[0].error == "unavailable"
    r.close()


def test_area_only_requires_opt_in():
    r = Registry([spec()])
    r.instances["test"] = Adapter(
        [
            Listing(
                "test",
                "1",
                "Town candidate",
                latitude=40.553,
                longitude=14.218,
                location_precision="area_only",
            )
        ]
    )
    engine = SearchEngine(r)
    q = SearchQuery(40.553, 14.218, 1000)
    assert not engine.search(q).results
    assert engine.search(replace(q, include_unlocated=True)).results[0].radius_match == "unverified"
    r.close()


def test_load_failure_is_isolated_and_secret_not_logged():
    r = Registry([spec("bad"), spec("good")])
    r.instances["bad"] = Adapter(RuntimeError("token=secret"))
    r.instances["good"] = Adapter([])
    report = SearchEngine(r).search(SearchQuery(40.553, 14.218))
    assert report.status == "partial" and "secret" not in json.dumps(report.to_dict())
    r.close()


def test_unsupported_country_and_disabled_sources():
    r = Registry()
    assert SearchEngine(r).search(SearchQuery(48.85, 2.35)).status == "unsupported"
    assert [s.source for s in r.relevant("IT")] == ["demanio"]
    assert r.relevant("IT", sources=["idealista"]) == []
    with pytest.raises(ValueError):
        r.relevant("IT", sources=["typo"])
    r.close()


def test_registry_config_paths_and_no_secrets(tmp_path):
    data = {**spec().__dict__, "options": {"location": "feed.xml"}}
    path = tmp_path / "sources.json"
    path.write_text(json.dumps([data]))
    r = Registry([])
    r.add_config(str(path))
    assert r.specs[0].options["location"] == str(tmp_path / "feed.xml")
    assert "options" not in r.to_dict()[0]
    with pytest.raises(ValueError):
        r.add_config(str(path))
    r.close()


@pytest.mark.parametrize(
    "changes",
    [
        {"source": "bad name"},
        {"status": "made-up"},
        {"country_codes": []},
        {"adapter": "os:system"},
        {"review": ""},
        {"property_types": ["castle"]},
    ],
)
def test_invalid_registry(changes):
    with pytest.raises(ValueError):
        replace(spec(), **changes)


@pytest.mark.parametrize(
    "args",
    [
        ["search"],
        ["search", "--lat", "1"],
        ["search", "--lat", "nan", "--lon", "1"],
        ["search", "--location", "Anacapri", "--lat", "40", "--lon", "14"],
        ["search", "--location", "Anacapri", "--radius", "-1"],
    ],
)
def test_cli_invalid_input(args, capsys):
    assert main(args) == 2
    assert "itsfs:" in capsys.readouterr().err


def test_cli_sources_and_unsupported_json(capsys):
    assert main(["sources", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["source"] == "demanio"
    assert main(["search", "--lat", "48.85", "--lon", "2.35", "--json"]) == 3
    assert json.loads(capsys.readouterr().out)["status"] == "unsupported"


def test_cli_synthetic_multisource_example(tmp_path, capsys, fixture_bytes):
    (tmp_path / "feed.xml").write_bytes(fixture_bytes("kyero.xml"))
    entries = [
        {
            **spec(s).__dict__,
            "property_types": ["residential", "land", "commercial", "other"],
            "options": {"location": "feed.xml"},
        }
        for s in ("agency_a", "agency_b")
    ]
    config = tmp_path / "sources.json"
    config.write_text(json.dumps(entries))
    args = [
        "search",
        "--lat",
        "40.553",
        "--lon",
        "14.218",
        "--radius",
        "2km",
        "--config",
        str(config),
        "--source",
        "agency_a",
        "--source",
        "agency_b",
        "--json",
    ]
    assert main(args) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["country"] == "IT" and len(report["sources"]) == 2
    assert len(report["results"]) == 4  # two URL merges; unlinked shops stay distinct
    assert report["results"][0]["duplicates"]
