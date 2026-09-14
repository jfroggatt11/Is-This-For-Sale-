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
