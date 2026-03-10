"""
Integration test suite: Navigation (broadcast ephemeris) products via unified config-based query interface.

Metadata
--------
Dates under test:
    RINEX v3: 2025-01-01  (DOY 001) - modern merged broadcast
    RINEX v2: 2010-01-01  (DOY 001) - legacy per-constellation
Products probed : RINEX3_NAV, RINEX2_NAV
Sources         : WUHAN, CDDIS, IGS

Usage
-----
Run all integration tests::

    uv run pytest test/test_navigation_resources.py -v

Skip in offline environments::

    uv run pytest -m "not integration"
"""
from __future__ import annotations

import datetime
import logging
from typing import List

import pytest

from gnss_ppp_products.data_query import query, ProductType, ProductQuality
from gnss_ppp_products.resources.resource import RemoteProductAddress

log = logging.getLogger(__name__)

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Test parameters
# ---------------------------------------------------------------------------

# RINEX v3 merged broadcast
DATE_RINEX3 = datetime.date(2025, 1, 1)
DOY_RINEX3: int = DATE_RINEX3.timetuple().tm_yday

# RINEX v2 legacy format (older date)
DATE_RINEX2 = datetime.date(2010, 1, 1)
DOY_RINEX2: int = DATE_RINEX2.timetuple().tm_yday

# Sources with navigation products
NAV_SOURCES = ["WUHAN", "CDDIS", "IGS"]


# ---------------------------------------------------------------------------
# Wuhan Navigation Tests
# ---------------------------------------------------------------------------


class TestWuhanNavigation:
    """Tests for Wuhan navigation products via unified interface."""

    SOURCE = "WUHAN"

    def test_rinex3_nav_found(self) -> None:
        """RINEX v3 merged broadcast should be available from Wuhan."""
        log.info("Testing %s RINEX3_NAV for %s (DOY %03d)", self.SOURCE, DATE_RINEX3, DOY_RINEX3)
        results = query(date=DATE_RINEX3, product_type=ProductType.RINEX3_NAV, source=self.SOURCE)
        assert len(results) > 0, f"No RINEX3_NAV found from {self.SOURCE}"
        product = results[0]
        assert product.type == ProductType.RINEX3_NAV
        assert "BRDC" in product.filename or "rnx" in product.filename.lower()
        log.info("[%s] RINEX3_NAV: %s", self.SOURCE, product.filename)

    def test_rinex3_directory_structure(self) -> None:
        """Navigation directory should contain year and DOY."""
        results = query(date=DATE_RINEX3, product_type=ProductType.RINEX3_NAV, source=self.SOURCE)
        assert len(results) > 0
        directory = results[0].directory
        assert "2025" in directory
        assert "001" in directory or "25p" in directory

    def test_rinex3_filename_has_date(self) -> None:
        """Navigation filename should contain date identifiers."""
        results = query(date=DATE_RINEX3, product_type=ProductType.RINEX3_NAV, source=self.SOURCE)
        assert len(results) > 0
        filename = results[0].filename
        year = str(DATE_RINEX3.year)
        doy = f"{DOY_RINEX3:03d}"
        assert year in filename or doy in filename, (
            f"Filename '{filename}' missing date (year={year}, doy={doy})"
        )


# ---------------------------------------------------------------------------
# CDDIS Navigation Tests
# ---------------------------------------------------------------------------


class TestCDDISNavigation:
    """Tests for CDDIS navigation products via unified interface."""

    SOURCE = "CDDIS"

    def test_rinex3_nav_query(self) -> None:
        """RINEX v3 navigation should be queryable from CDDIS."""
        log.info("Testing %s RINEX3_NAV for %s", self.SOURCE, DATE_RINEX3)
        results = query(date=DATE_RINEX3, product_type=ProductType.RINEX3_NAV, source=self.SOURCE)
        # CDDIS requires FTPS, may not connect in all environments
        if len(results) > 0:
            assert results[0].type == ProductType.RINEX3_NAV
            log.info("[%s] RINEX3_NAV: %s", self.SOURCE, results[0].filename)
        else:
            log.warning("[%s] RINEX3_NAV not found (FTPS may be required)", self.SOURCE)

    def test_rinex2_nav_query(self) -> None:
        """RINEX v2 GPS navigation should be queryable from CDDIS."""
        log.info("Testing %s RINEX2_NAV for %s", self.SOURCE, DATE_RINEX2)
        results = query(date=DATE_RINEX2, product_type=ProductType.RINEX2_NAV, source=self.SOURCE)
        if len(results) > 0:
            assert results[0].type == ProductType.RINEX2_NAV
            log.info("[%s] RINEX2_NAV: %s", self.SOURCE, results[0].filename)
        else:
            log.warning("[%s] RINEX2_NAV not found (FTPS may be required)", self.SOURCE)

    def test_rinex2_directory_structure(self) -> None:
        """RINEX v2 directory should contain year/DOY path."""
        results = query(date=DATE_RINEX2, product_type=ProductType.RINEX2_NAV, source=self.SOURCE)
        if len(results) > 0:
            directory = results[0].directory
            assert "2010" in directory


# ---------------------------------------------------------------------------
# IGS Navigation Tests
# ---------------------------------------------------------------------------


class TestIGSNavigation:
    """Tests for IGS navigation products via unified interface."""

    SOURCE = "IGS"

    def test_rinex3_nav_found(self) -> None:
        """RINEX v3 merged broadcast should be available from IGS."""
        log.info("Testing %s RINEX3_NAV for %s", self.SOURCE, DATE_RINEX3)
        results = query(date=DATE_RINEX3, product_type=ProductType.RINEX3_NAV, source=self.SOURCE)
        assert len(results) > 0, f"No RINEX3_NAV found from {self.SOURCE}"
        product = results[0]
        assert product.type == ProductType.RINEX3_NAV
        assert "BRDC" in product.filename
        log.info("[%s] RINEX3_NAV: %s", self.SOURCE, product.filename)


# ---------------------------------------------------------------------------
# Cross-Source Comparison
# ---------------------------------------------------------------------------


class TestCrossSourceNavAvailability:
    """Test navigation products across multiple sources."""

    @pytest.fixture(scope="class")
    def all_nav_results(self) -> dict[str, List[RemoteProductAddress]]:
        results = {}
        for source in ["WUHAN", "IGS"]:
            try:
                r = query(date=DATE_RINEX3, product_type=ProductType.RINEX3_NAV, source=source)
                results[source] = r
            except Exception as e:
                log.warning("[%s] RINEX3_NAV query error: %s", source, e)
                results[source] = []
        return results

    def test_at_least_one_source_has_nav(self, all_nav_results) -> None:
        """RINEX3 NAV should be available from at least 1 source."""
        available = [s for s, r in all_nav_results.items() if len(r) > 0]
        log.info("RINEX3_NAV available from: %s", available)
        assert len(available) >= 1, f"RINEX3_NAV not found from any source"

    def test_all_results_correct_type(self, all_nav_results) -> None:
        """All returned products must have RINEX3_NAV type."""
        for source, results in all_nav_results.items():
            for product in results:
                assert product.type == ProductType.RINEX3_NAV


# ---------------------------------------------------------------------------
# Product Type Existence
# ---------------------------------------------------------------------------


class TestNavigationProductTypes:
    """Verify navigation product types exist."""

    def test_rinex3_nav_exists(self) -> None:
        assert ProductType.RINEX3_NAV is not None
        assert ProductType.RINEX3_NAV.value == "RINEX3_NAV"

    def test_rinex2_nav_exists(self) -> None:
        assert ProductType.RINEX2_NAV is not None
        assert ProductType.RINEX2_NAV.value == "RINEX2_NAV"
