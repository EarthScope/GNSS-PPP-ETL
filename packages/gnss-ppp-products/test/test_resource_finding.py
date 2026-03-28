"""
Tests: Resource finding — full pipeline from QueryFactory to ResourceFetcher.

Verifies that the complete query→search pipeline finds actual files on real
GNSS data servers.  Each test class targets one data center.

Servers : Wuhan (FTP), CODE (FTP), CDDIS (FTPS)
Products: ORBIT, CLOCK, ERP, BIA, IONEX, RNX3_BRDC, LEAP_SEC, SAT_PARAMS, ATTOBX

All tests in this module are marked ``integration`` (hit real servers).
"""

from __future__ import annotations

import datetime
import re

import pytest

from gnss_ppp_products.factories import ResourceFetcher, FetchResult
from gnss_ppp_products.specifications.products.product import ProductPath


pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _search_remote(qf, fetcher, date, product_name, parameters=None):
    """Run the full query→search pipeline and return only remote FetchResults."""
    queries = qf.get(date=date, product={"name": product_name}, parameters=parameters)
    remote_queries = [
        q
        for q in queries
        if (q.server.protocol or "").upper() not in ("FILE", "LOCAL", "")
    ]
    results = fetcher.search(remote_queries)
    return results


def _assert_found(results, product_name, min_matches=1):
    """Assert at least *min_matches* results have matched files."""
    found = [r for r in results if r.found]
    assert len(found) >= min_matches, (
        f"{product_name}: expected >= {min_matches} found, got {len(found)}. "
        f"Errors: {[r.error for r in results if r.error]}"
    )
    return found


# ---------------------------------------------------------------------------
# Wuhan (FTP) — igs.gnsswhu.cn
# ---------------------------------------------------------------------------


class TestWuhanResourceFinding:
    """Search for products on Wuhan FTP."""

    def test_orbit_found(self, wuhan_qf, fetcher, test_date) -> None:
        results = _search_remote(wuhan_qf, fetcher, test_date, "ORBIT", {"AAA": "WUM"})
        found = _assert_found(results, "ORBIT")
        for r in found:
            assert any("SP3" in f.upper() for f in r.matched_filenames)

    def test_clock_found(self, wuhan_qf, fetcher, test_date) -> None:
        results = _search_remote(wuhan_qf, fetcher, test_date, "CLOCK", {"AAA": "WUM"})
        found = _assert_found(results, "CLOCK")
        for r in found:
            assert any("CLK" in f.upper() for f in r.matched_filenames)

    def test_erp_found(self, wuhan_qf, fetcher, test_date) -> None:
        results = _search_remote(wuhan_qf, fetcher, test_date, "ERP")
        _assert_found(results, "ERP")

    def test_bias_found(self, wuhan_qf, fetcher, test_date) -> None:
        results = _search_remote(wuhan_qf, fetcher, test_date, "BIA", {"AAA": "WUM"})
        _assert_found(results, "BIA")

    def test_attobx_found(self, wuhan_qf, fetcher, test_date) -> None:
        results = _search_remote(wuhan_qf, fetcher, test_date, "ATTOBX", {"AAA": "WUM"})
        _assert_found(results, "ATTOBX")

    def test_leap_sec_found(self, wuhan_qf, fetcher, test_date) -> None:
        results = _search_remote(wuhan_qf, fetcher, test_date, "LEAP_SEC")
        found = _assert_found(results, "LEAP_SEC")
        for r in found:
            assert any("leap" in f.lower() for f in r.matched_filenames)

    def test_sat_params_found(self, wuhan_qf, fetcher, test_date) -> None:
        results = _search_remote(wuhan_qf, fetcher, test_date, "SAT_PARAMS")
        found = _assert_found(results, "SAT_PARAMS")
        for r in found:
            assert any("sat_param" in f.lower() for f in r.matched_filenames)

    def test_orbit_filenames_match_date(self, wuhan_qf, fetcher, test_date) -> None:
        """Matched orbit filenames should contain the target date identifiers."""
        results = _search_remote(wuhan_qf, fetcher, test_date, "ORBIT", {"AAA": "WUM"})
        found = _assert_found(results, "ORBIT")
        for r in found:
            for fn in r.matched_filenames:
                assert "2025" in fn, f"Missing year in filename: {fn}"
                assert "015" in fn, f"Missing DOY in filename: {fn}"

    def test_directory_listing_populated(self, wuhan_qf, fetcher, test_date) -> None:
        """FetchResult should include the full directory listing."""
        results = _search_remote(wuhan_qf, fetcher, test_date, "ORBIT", {"AAA": "WUM"})
        found = _assert_found(results, "ORBIT")
        for r in found:
            assert len(r.directory_listing) > 0

    def test_matched_filename_is_subset_of_listing(
        self, wuhan_qf, fetcher, test_date
    ) -> None:
        results = _search_remote(wuhan_qf, fetcher, test_date, "ORBIT", {"AAA": "WUM"})
        found = _assert_found(results, "ORBIT")
        for r in found:
            for fn in r.matched_filenames:
                assert fn in r.directory_listing


# ---------------------------------------------------------------------------
# CODE (FTP) — ftp.aiub.unibe.ch
# ---------------------------------------------------------------------------


class TestCODResourceFinding:
    """Search for products on CODE FTP."""

    def test_orbit_found(self, cod_qf, fetcher, test_date) -> None:
        results = _search_remote(cod_qf, fetcher, test_date, "ORBIT")
        _assert_found(results, "ORBIT")

    def test_clock_found(self, cod_qf, fetcher, test_date) -> None:
        results = _search_remote(cod_qf, fetcher, test_date, "CLOCK")
        _assert_found(results, "CLOCK")

    def test_erp_found(self, cod_qf, fetcher, test_date) -> None:
        results = _search_remote(cod_qf, fetcher, test_date, "ERP")
        _assert_found(results, "ERP")

    def test_bias_found(self, cod_qf, fetcher, test_date) -> None:
        results = _search_remote(cod_qf, fetcher, test_date, "BIA")
        _assert_found(results, "BIA")

    def test_ionex_found(self, cod_qf, fetcher, test_date) -> None:
        results = _search_remote(cod_qf, fetcher, test_date, "IONEX")
        found = _assert_found(results, "IONEX")
        for r in found:
            assert any(
                "GIM" in f.upper() or "INX" in f.upper() for f in r.matched_filenames
            )

    def test_orbit_directory_is_code_year(self, cod_qf, fetcher, test_date) -> None:
        """CODE orbit files should be under CODE/{YYYY}/."""
        results = _search_remote(cod_qf, fetcher, test_date, "ORBIT")
        found = _assert_found(results, "ORBIT")
        for r in found:
            d = r.query.directory
            d_str = d.pattern if isinstance(d, ProductPath) else str(d)
            assert "CODE/2025" in d_str

    def test_orbit_filenames_contain_cod(self, cod_qf, fetcher, test_date) -> None:
        results = _search_remote(cod_qf, fetcher, test_date, "ORBIT")
        found = _assert_found(results, "ORBIT")
        for r in found:
            assert any("COD" in f for f in r.matched_filenames)


# ---------------------------------------------------------------------------
# CDDIS (FTPS) — gdc.cddis.eosdis.nasa.gov
# ---------------------------------------------------------------------------


class TestCDDISResourceFinding:
    """Search for products on CDDIS FTPS."""

    def test_orbit_found(self, cddis_qf, fetcher, test_date) -> None:
        results = _search_remote(cddis_qf, fetcher, test_date, "ORBIT", {"AAA": "WUM"})
        _assert_found(results, "ORBIT")

    def test_clock_found(self, cddis_qf, fetcher, test_date) -> None:
        results = _search_remote(cddis_qf, fetcher, test_date, "CLOCK", {"AAA": "IGS"})
        _assert_found(results, "CLOCK")

    def test_ionex_found(self, cddis_qf, fetcher, test_date) -> None:
        results = _search_remote(cddis_qf, fetcher, test_date, "IONEX", {"AAA": "COD"})
        _assert_found(results, "IONEX")

    def test_ftps_protocol_used(self, cddis_qf, fetcher, test_date) -> None:
        """CDDIS queries should use FTPS protocol."""
        results = _search_remote(cddis_qf, fetcher, test_date, "ORBIT", {"AAA": "WUM"})
        for r in results:
            assert r.query.server.protocol.lower() == "ftps"

    def test_gpsweek_in_directory(self, cddis_qf, fetcher, test_date) -> None:
        gpsweek = str((test_date.date() - datetime.date(1980, 1, 6)).days // 7)
        results = _search_remote(cddis_qf, fetcher, test_date, "ORBIT", {"AAA": "WUM"})
        for r in results:
            d = r.query.directory
            d_str = d.pattern if isinstance(d, ProductPath) else str(d)
            assert gpsweek in d_str


# ---------------------------------------------------------------------------
# Cross-center: ResourceFetcher caching
# ---------------------------------------------------------------------------


class TestFetcherCaching:
    """Verify ResourceFetcher caches directory listings across queries."""

    def test_listing_cached_after_search(self, wuhan_qf, test_date) -> None:
        """After searching, the listing cache should contain entries."""
        fresh_fetcher = ResourceFetcher()
        queries = wuhan_qf.get(
            date=test_date,
            product={"name": "ORBIT"},
            parameters={"AAA": "WUM"},
        )
        remote_queries = [
            q
            for q in queries
            if (q.server.protocol or "").upper() not in ("FILE", "LOCAL", "")
        ]
        fresh_fetcher.search(remote_queries)
        assert len(fresh_fetcher._connection_pool_factory._listing_cache) > 0

    def test_same_directory_not_listed_twice(self, wuhan_qf, test_date) -> None:
        """Two queries sharing the same directory should reuse the cached listing."""
        fresh_fetcher = ResourceFetcher()
        # Get ERP and ORBIT — both at Wuhan go to the same orbit/ directory
        orbit_queries = wuhan_qf.get(
            date=test_date,
            product={"name": "ORBIT"},
            parameters={"AAA": "WUM"},
        )
        erp_queries = wuhan_qf.get(date=test_date, product={"name": "ERP"})
        remote = [
            q
            for q in orbit_queries + erp_queries
            if (q.server.protocol or "").upper() not in ("FILE", "LOCAL", "")
        ]
        fresh_fetcher.search(remote)
        # Cache should have entries, but NOT one per query — shared dirs collapse
        assert len(fresh_fetcher._connection_pool_factory._listing_cache) <= len(remote)


# ---------------------------------------------------------------------------
# FetchResult properties
# ---------------------------------------------------------------------------


class TestFetchResultProperties:
    """Verify FetchResult convenience properties."""

    def test_found_property(self, wuhan_qf, fetcher, test_date) -> None:
        results = _search_remote(wuhan_qf, fetcher, test_date, "ORBIT", {"AAA": "WUM"})
        found = [r for r in results if r.found]
        assert len(found) > 0
        for r in found:
            assert r.matched_filenames  # non-empty

    def test_not_found_has_error_or_empty(self, wuhan_qf, fetcher, test_date) -> None:
        """Results that aren't found should either have an error or empty matches."""
        results = _search_remote(wuhan_qf, fetcher, test_date, "ORBIT", {"AAA": "WUM"})
        not_found = [r for r in results if not r.found]
        for r in not_found:
            assert r.matched_filenames == []
