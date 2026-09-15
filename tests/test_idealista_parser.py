from datetime import UTC, datetime
from pathlib import Path

import pytest

from itsfs.adapters.base import SourceChanged
from itsfs.parsers.idealista import parse_detail

BODY = (Path(__file__).parent / "fixtures/idealista_detail.html").read_text()
URL = "https://www.idealista.it/immobile/101/"
CAPTURED = datetime(2026, 9, 15, 10, 40, tzinfo=UTC)


def test_observed_schema_and_capture_provenance():
    row = parse_detail(BODY, URL, captured_at=CAPTURED)
    assert row.source == "idealista" and row.source_id == "101"
    assert row.price == 245000 and row.currency == "EUR"
    assert row.area_m2 == 85 and row.raw["usable_area_m2"] == 72
    assert row.raw["rooms"] == 3 and row.bedrooms is None
    assert row.raw["bathrooms"] == 2
    assert row.address == "Via Esempio, 9" and row.municipality == "Firenze"
    assert row.latitude is None and row.longitude is None and row.location_precision == "unknown"
    assert row.description is None and "private note" not in str(row.to_dict())
    assert row.retrieved_at == CAPTURED


@pytest.mark.parametrize("price", ["Su richiesta", "245.000 USD", "245..000 €"])
def test_unrecognized_price_is_not_inferred_from_fees_or_unit_price(price):
    row = parse_detail(BODY.replace("245.000 €", price), URL, captured_at=CAPTURED)
    assert row.price is None and row.currency is None and row.raw["parser_warnings"]


@pytest.mark.parametrize(
    "body",
    [
        "<h1>Device check</h1>",
        BODY.replace("main-info__title-main", "changed-title"),
        BODY.replace("in vendita", "in affitto"),
        BODY.replace("in vendita", "all'asta"),
        BODY.replace("Via Esempio, 9", "asta - Via Esempio, 9"),
        BODY.replace("Trilocale", "Terreno agricolo"),
    ],
)
def test_challenge_changed_schema_and_unsupported_sale_rejected(body):
    with pytest.raises(SourceChanged):
        parse_detail(body, URL, captured_at=CAPTURED)


@pytest.mark.parametrize(
    "url",
    [
        "http://www.idealista.it/immobile/101/",
        "https://evil.invalid/immobile/101/",
        URL + "?token=secret",
        URL + "#x",
        "https://user@www.idealista.it/immobile/101/",
        "https://www.idealista.it/vendita-case/firenze-firenze/",
    ],
)
def test_url_identity_validation(url):
    with pytest.raises(ValueError):
        parse_detail(BODY, url, captured_at=CAPTURED)


def test_missing_optional_fields_and_ambiguous_location():
    row = parse_detail(
        BODY.replace("85 m² commerciali, 72 m² calpestabili", "").replace(
            "<li>Quartiere Esempio</li>", ""
        ),
        URL,
        captured_at=CAPTURED,
    )
    assert row.area_m2 is None and row.address is None and row.municipality is None
    assert row.raw["parser_warnings"]


def test_conflicting_prices_fail_closed():
    extra = (
        '<p class="flex-feature"><span class="flex-feature-details">'
        "Prezzo dell'immobile:</span>"
        '<strong class="flex-feature-details">300.000 €</strong></p>'
    )
    with pytest.raises(SourceChanged):
        parse_detail(BODY + extra, URL, captured_at=CAPTURED)


def test_capture_time_not_replaced_by_parse_time():
    with pytest.raises(ValueError):
        parse_detail(BODY, URL, captured_at=CAPTURED.replace(tzinfo=None))
    assert (
        parse_detail(BODY, URL, captured_at=CAPTURED).to_dict()["retrieved_at"]
        == CAPTURED.isoformat()
    )
