"""
Tests: Antenna phase center (ANTEX) products via QueryFactory.

Products: ATTATX
Centers : IGS (HTTPS via files.igs.org)
"""

from __future__ import annotations

import pytest

from gnss_ppp_products.factories import ResourceFetcher, FetchResult


pytestmark = pytest.mark.integration


def _get_remote_queries(qf, date, product_name, parameters=None):
    queries = qf.get(date=date, product={"name": product_name}, parameters=parameters)
    return [
        q
        for q in queries
        if (q.server.protocol or "").upper() not in ("FILE", "LOCAL", "")
    ]


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
# Unit: IGS ANTEX query expansion
# ---------------------------------------------------------------------------


class TestIGSAntexExpansion:
    def test_attatx_queries_returned(self, igs_qf, test_date) -> None:
        queries = _get_remote_queries(igs_qf, test_date, "ATTATX")
        assert len(queries) > 0

    def test_attatx_server_protocol_is_https(self, igs_qf, test_date) -> None:
        queries = _get_remote_queries(igs_qf, test_date, "ATTATX")
        for q in queries:
            assert q.server.protocol.lower() == "https"

    def test_attatx_filename_contains_atx(self, igs_qf, test_date) -> None:
        queries = _get_remote_queries(igs_qf, test_date, "ATTATX")
        patterns = [q.product.filename.pattern for q in queries]
        assert any("atx" in p.lower() for p in patterns)


# ---------------------------------------------------------------------------
# Integration: IGS ANTEX probe
# ---------------------------------------------------------------------------


class TestIGSAntexProbe:
    def test_attatx_found(self, igs_qf, fetcher, test_date) -> None:
        results = _search_remote(igs_qf, fetcher, test_date, "ATTATX")
        _assert_found(results, "ATTATX")

    def test_attatx_filenames_contain_atx(self, igs_qf, fetcher, test_date) -> None:
        results = _search_remote(igs_qf, fetcher, test_date, "ATTATX")
        found = _assert_found(results, "ATTATX")
        for r in found:
            assert any("atx" in f.lower() for f in r.matched_filenames)
