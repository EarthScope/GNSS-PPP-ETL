"""
Tests: Broadcast navigation products via QueryFactory.

Products: RNX3_BRDC
Centers : Wuhan (FTP), CDDIS (FTPS)
"""
from __future__ import annotations

import pytest

from gnss_ppp_products.factories import ResourceFetcher, FetchResult


pytestmark = pytest.mark.integration


def _get_remote_queries(qf, date, product_name, parameters=None):
    queries = qf.get(date=date, product={"name": product_name}, parameters=parameters)
    return [q for q in queries if (q.server.protocol or "").upper() not in ("FILE", "LOCAL", "")]


def _search_remote(qf, fetcher, date, product_name, parameters=None):
    queries = _get_remote_queries(qf, date, product_name, parameters)
    return fetcher.search(queries)


def _assert_found(results, product_name, min_matches=1):
    found = [r for r in results if r.found]
    assert len(found) >= min_matches, (
        f"{product_name}: expected >= {min_matches} found, got {len(found)}. "
        f"Errors: {[r.error for r in results if r.error]}"
    )
    return found


# ---------------------------------------------------------------------------
# Unit: Wuhan broadcast navigation
# ---------------------------------------------------------------------------

class TestWuhanNavigationExpansion:

    def test_brdc_queries_returned(self, wuhan_qf, test_date) -> None:
        queries = _get_remote_queries(wuhan_qf, test_date, "RNX3_BRDC")
        assert len(queries) > 0

    def test_brdc_server_protocol(self, wuhan_qf, test_date) -> None:
        queries = _get_remote_queries(wuhan_qf, test_date, "RNX3_BRDC")
        for q in queries:
            assert q.server.protocol.lower() == "ftp"

    def test_brdc_directory_not_empty(self, wuhan_qf, test_date) -> None:
        queries = _get_remote_queries(wuhan_qf, test_date, "RNX3_BRDC")
        for q in queries:
            d = q.directory.value or q.directory.pattern
            assert len(d) > 0

    def test_brdc_filename_contains_brdc(self, wuhan_qf, test_date) -> None:
        queries = _get_remote_queries(wuhan_qf, test_date, "RNX3_BRDC")
        patterns = [q.product.filename.pattern for q in queries]
        assert any("BRDC" in p for p in patterns)


# ---------------------------------------------------------------------------
# Unit: CDDIS broadcast navigation
# ---------------------------------------------------------------------------

class TestCDDISNavigationExpansion:

    def test_brdc_queries_returned(self, cddis_qf, test_date) -> None:
        queries = _get_remote_queries(cddis_qf, test_date, "RNX3_BRDC")
        assert len(queries) > 0

    def test_brdc_protocol_is_ftps(self, cddis_qf, test_date) -> None:
        queries = _get_remote_queries(cddis_qf, test_date, "RNX3_BRDC")
        for q in queries:
            assert q.server.protocol.lower() == "ftps"

    def test_brdc_filename_contains_brdc(self, cddis_qf, test_date) -> None:
        queries = _get_remote_queries(cddis_qf, test_date, "RNX3_BRDC")
        patterns = [q.product.filename.pattern for q in queries]
        assert any("BRDC" in p for p in patterns)


# ---------------------------------------------------------------------------
# Integration: Wuhan navigation probe
# ---------------------------------------------------------------------------

class TestWuhanNavigationProbe:

    def test_brdc_found(self, wuhan_qf, fetcher, test_date) -> None:
        results = _search_remote(wuhan_qf, fetcher, test_date, "RNX3_BRDC")
        _assert_found(results, "RNX3_BRDC")

    def test_brdc_filenames_contain_brdc(self, wuhan_qf, fetcher, test_date) -> None:
        results = _search_remote(wuhan_qf, fetcher, test_date, "RNX3_BRDC")
        found = _assert_found(results, "RNX3_BRDC")
        for r in found:
            assert any("BRDC" in f for f in r.matched_filenames)


# ---------------------------------------------------------------------------
# Integration: CDDIS navigation probe
# ---------------------------------------------------------------------------

class TestCDDISNavigationProbe:

    def test_brdc_found(self, cddis_qf, fetcher, test_date) -> None:
        results = _search_remote(cddis_qf, fetcher, test_date, "RNX3_BRDC")
        _assert_found(results, "RNX3_BRDC")
