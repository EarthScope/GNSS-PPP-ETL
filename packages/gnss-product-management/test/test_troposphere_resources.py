"""
Tests: Troposphere (VMF) products via QueryFactory.

Products: VMF
Centers : VMF / TU Wien (HTTPS)
"""

from __future__ import annotations

import pytest

from gnss_product_management.factories import ResourceFetcher, FetchResult


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
# Unit: VMF query expansion
# ---------------------------------------------------------------------------


class TestVMFExpansion:
    def test_vmf_queries_returned(self, vmf_qf, test_date) -> None:
        queries = _get_remote_queries(vmf_qf, test_date, "VMF")
        assert len(queries) > 0

    def test_vmf_server_protocol_is_https(self, vmf_qf, test_date) -> None:
        queries = _get_remote_queries(vmf_qf, test_date, "VMF")
        for q in queries:
            assert q.server.protocol.lower() == "https"

    def test_vmf_directory_not_empty(self, vmf_qf, test_date) -> None:
        queries = _get_remote_queries(vmf_qf, test_date, "VMF")
        for q in queries:
            d = q.directory.value or q.directory.pattern
            assert len(d) > 0

    def test_vmf_multiple_resolutions(self, vmf_qf, test_date) -> None:
        """VMF center should produce queries for multiple grid resolutions."""
        queries = _get_remote_queries(vmf_qf, test_date, "VMF")
        assert len(queries) >= 2


# ---------------------------------------------------------------------------
# Integration: VMF HTTPS probe
# ---------------------------------------------------------------------------


class TestVMFProbe:
    def test_vmf_found(self, vmf_qf, fetcher, test_date) -> None:
        results = _search_remote(vmf_qf, fetcher, test_date, "VMF")
        _assert_found(results, "VMF")

    def test_vmf_filenames_contain_vmf(self, vmf_qf, fetcher, test_date) -> None:
        results = _search_remote(vmf_qf, fetcher, test_date, "VMF")
        found = _assert_found(results, "VMF")
        for r in found:
            assert any(
                "VMF" in f.upper() or "vmf" in f.lower() for f in r.matched_filenames
            )
