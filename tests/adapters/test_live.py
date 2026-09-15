"""Run explicitly with ITSFS_LIVE=1 pytest -m live; no credentials needed."""

import os

import pytest

from itsfs.adapters.italy.demanio import BASE, DemanioAdapter
from itsfs.http import PoliteHTTP


@pytest.mark.live
@pytest.mark.skipif(os.environ.get("ITSFS_LIVE") != "1", reason="live tests are opt-in")
def test_public_sale_search_and_optional_detail():
    http = PoliteHTTP("IsThisForSale/0.1 (opt-in adapter smoke test)")
    try:
        adapter = DemanioAdapter(http)
        urls, count = adapter.parse_search(
            http.get(BASE + "/AsteDemanio/sito.php/ricerca/?f_ricerca=vendite&f_regione=09&f_np=1")
        )
        assert count >= 0
        if urls:
            listing = adapter.parse_detail(http.get(urls[0]), urls[0])
            assert listing is None or listing.source == "demanio"  # may have expired
    finally:
        http.close()


@pytest.mark.live
@pytest.mark.skipif(os.environ.get("ITSFS_LIVE") != "1", reason="live tests are opt-in")
def test_risorse_public_catalogue_and_one_detail():
    from itsfs.adapters.italy.risorseimmobiliari import BASE as RISORSE_BASE
    from itsfs.adapters.italy.risorseimmobiliari import RisorseimmobiliariAdapter

    http = PoliteHTTP("IsThisForSale/0.1 (opt-in adapter smoke test)")
    try:
        adapter = RisorseimmobiliariAdapter(http)
        url = RISORSE_BASE + "/Firenze/case_in-vendita_Firenze.html"
        urls, _ = adapter.parse_search(http.get(url), url)
        if urls:
            listing = adapter.parse_detail(http.get(urls[0]), urls[0])
            assert listing is None or listing.source == "risorseimmobiliari"
    finally:
        http.close()


@pytest.mark.live
@pytest.mark.skipif(os.environ.get("ITSFS_LIVE") != "1", reason="live tests are opt-in")
def test_caasa_public_search_in_another_city():
    from itsfs.adapters.italy.caasa import CaasaAdapter

    http = PoliteHTTP("IsThisForSale/0.1 (opt-in adapter smoke test)", min_interval=2)
    try:
        results = CaasaAdapter(http, max_pages=1, max_cities=1).search(
            45.85, 9.39, 2000, ["residential"]
        )
        assert all(x.source == "caasa" for x in results)
    finally:
        http.close()
