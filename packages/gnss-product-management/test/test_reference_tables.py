"""
Tests: Reference table products via SearchPlanner.

Products: LEAP_SEC, SAT_PARAMS
Centers : Wuhan (FTP)
"""

from __future__ import annotations

import pytest


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
    found = [r for r in results if r.product.filename and r.product.filename.value]
    assert len(found) >= min_matches, (
        f"{product_name}: expected >= {min_matches} found, got {len(found)} "
        f"out of {len(results)} results."
    )
    return found


# ---------------------------------------------------------------------------
# Unit: Reference table query expansion
# ---------------------------------------------------------------------------


class TestReferenceTableExpansion:
    def test_leap_sec_queries_returned(self, wuhan_qf, test_date) -> None:
        queries = _get_remote_queries(wuhan_qf, test_date, "LEAP_SEC")
        assert len(queries) > 0

    def test_leap_sec_filename_pattern(self, wuhan_qf, test_date) -> None:
        queries = _get_remote_queries(wuhan_qf, test_date, "LEAP_SEC")
        patterns = [q.product.filename.pattern for q in queries]
        assert any("leap" in p.lower() for p in patterns)

    def test_sat_params_queries_returned(self, wuhan_qf, test_date) -> None:
        queries = _get_remote_queries(wuhan_qf, test_date, "SAT_PARAMS")
        assert len(queries) > 0

    def test_sat_params_filename_pattern(self, wuhan_qf, test_date) -> None:
        queries = _get_remote_queries(wuhan_qf, test_date, "SAT_PARAMS")
        patterns = [q.product.filename.pattern for q in queries]
        assert any("sat_param" in p.lower() for p in patterns)

    def test_leap_sec_server_is_ftp(self, wuhan_qf, test_date) -> None:
        queries = _get_remote_queries(wuhan_qf, test_date, "LEAP_SEC")
        for q in queries:
            assert q.server.protocol.lower() == "ftp"


# ---------------------------------------------------------------------------
# Integration: Reference table probes
# ---------------------------------------------------------------------------


class TestReferenceTableProbe:
    def test_leap_sec_found(self, wuhan_qf, fetcher, test_date) -> None:
        results = _search_remote(wuhan_qf, fetcher, test_date, "LEAP_SEC")
        found = _assert_found(results, "LEAP_SEC")
        for r in found:
            assert any("leap" in f.lower() for f in [r.product.filename.value])

    def test_sat_params_found(self, wuhan_qf, fetcher, test_date) -> None:
        results = _search_remote(wuhan_qf, fetcher, test_date, "SAT_PARAMS")
        found = _assert_found(results, "SAT_PARAMS")
        for r in found:
            assert any("sat_param" in f.lower() for f in [r.product.filename.value])
