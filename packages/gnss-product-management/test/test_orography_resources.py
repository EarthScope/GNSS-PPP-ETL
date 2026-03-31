"""
Tests: Orography grid products via QueryFactory.

Products: OROGRAPHY
Centers : VMF / TU Wien (HTTPS)
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
    found = [r for r in results if r.found]
    assert len(found) >= min_matches, (
        f"{product_name}: expected >= {min_matches} found, got {len(found)}. "
        f"Errors: {[r.error for r in results if r.error]}"
    )
    return found


# ---------------------------------------------------------------------------
# Unit: Orography query expansion
# ---------------------------------------------------------------------------


class TestOrographyExpansion:
    def test_orography_queries_returned(self, vmf_qf, test_date) -> None:
        queries = _get_remote_queries(vmf_qf, test_date, "OROGRAPHY")
        assert len(queries) > 0

    def test_orography_server_protocol_is_https(self, vmf_qf, test_date) -> None:
        queries = _get_remote_queries(vmf_qf, test_date, "OROGRAPHY")
        for q in queries:
            assert q.server.protocol.lower() == "https"

    def test_orography_filename_pattern(self, vmf_qf, test_date) -> None:
        queries = _get_remote_queries(vmf_qf, test_date, "OROGRAPHY")
        patterns = [q.product.filename.pattern for q in queries]
        assert any("orog" in p.lower() or "ell" in p.lower() for p in patterns)

    def test_orography_at_least_one_query(self, vmf_qf, test_date) -> None:
        queries = _get_remote_queries(vmf_qf, test_date, "OROGRAPHY")
        assert len(queries) >= 1


# ---------------------------------------------------------------------------
# Integration: Orography HTTPS probe
# ---------------------------------------------------------------------------


class TestOrographyProbe:
    def test_orography_found(self, vmf_qf, fetcher, test_date) -> None:
        results = _search_remote(vmf_qf, fetcher, test_date, "OROGRAPHY")
        _assert_found(results, "OROGRAPHY")
