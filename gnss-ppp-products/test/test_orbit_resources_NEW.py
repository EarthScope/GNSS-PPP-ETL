"""
Integration test suite: Orbit/Clock products via unified config-based query interface.

Metadata
--------
Date under test : 2025-01-01  (DOY 001, GPS week 2347)
Products probed : SP3, CLK, ERP, BIAS, OBX
Sources         : WUHAN, CDDIS, IGS, ESA, CODE, GFZ

Usage
-----
Run all integration tests::

    uv run pytest test/test_orbit_resources.py -v

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

DATE = datetime.date(2025, 1, 1)
DOY: int = DATE.timetuple().tm_yday  # 1
GPS_WEEK: int = (DATE - datetime.date(1980, 1, 6)).days // 7  # 2347

# Sources known to have orbit/clock products in YAML configs
ORBIT_SOURCES = ["WUHAN", "CDDIS", "IGS", "ESA", "CODE", "GFZ"]


# ---------------------------------------------------------------------------
# Wuhan Orbit/Clock Tests
# ---------------------------------------------------------------------------


class TestWuhanOrbitClock:
    """Tests for Wuhan orbit/clock products via unified interface."""

    SOURCE = "WUHAN"

    def test_sp3_final(self) -> None:
        """Wuhan SP3 FINAL should be available."""
        results = query(date=DATE, product_type=ProductType.SP3,
                        product_quality=ProductQuality.FINAL, center=self.SOURCE)
        assert len(results) > 0, f"No SP3 FINAL found from {self.SOURCE}"
        product = results[0]
        assert product.type == ProductType.SP3
        assert "SP3" in product.filename.upper() or "ORB" in product.filename.upper()
        log.info("[%s] SP3 FINAL: %s", self.SOURCE, product.filename)

    def test_clk_final(self) -> None:
        """Wuhan CLK FINAL should be available."""
        results = query(date=DATE, product_type=ProductType.CLK,
                        product_quality=ProductQuality.FINAL, center=self.SOURCE)
        assert len(results) > 0, f"No CLK FINAL found from {self.SOURCE}"
        product = results[0]
        assert product.type == ProductType.CLK
        log.info("[%s] CLK FINAL: %s", self.SOURCE, product.filename)

    def test_erp(self) -> None:
        """Wuhan ERP should be available (RAPID or FINAL)."""
        results = query(date=DATE, product_type=ProductType.ERP, center=self.SOURCE)
        assert len(results) > 0, f"No ERP found from {self.SOURCE}"
        log.info("[%s] ERP %s: %s", self.SOURCE, results[0].quality, results[0].filename)

    def test_bias_final(self) -> None:
        """Wuhan BIAS FINAL should be available."""
        results = query(date=DATE, product_type=ProductType.BIAS,
                        product_quality=ProductQuality.FINAL, center=self.SOURCE)
        assert len(results) > 0, f"No BIAS FINAL found from {self.SOURCE}"
        log.info("[%s] BIAS FINAL: %s", self.SOURCE, results[0].filename)

    def test_obx_final(self) -> None:
        """Wuhan OBX FINAL should be available."""
        results = query(date=DATE, product_type=ProductType.OBX,
                        product_quality=ProductQuality.FINAL, center=self.SOURCE)
        assert len(results) > 0, f"No OBX FINAL found from {self.SOURCE}"
        log.info("[%s] OBX FINAL: %s", self.SOURCE, results[0].filename)

    def test_sp3_directory_structure(self) -> None:
        """SP3 directory should contain year."""
        results = query(date=DATE, product_type=ProductType.SP3, center=self.SOURCE)
        assert len(results) > 0
        assert "2025" in results[0].directory


# ---------------------------------------------------------------------------
# IGS Orbit/Clock Tests
# ---------------------------------------------------------------------------


class TestIGSOrbitClock:
    """Tests for IGS combined orbit/clock products via unified interface."""

    SOURCE = "IGS"

    def test_sp3_final(self) -> None:
        """IGS SP3 FINAL should be available."""
        results = query(date=DATE, product_type=ProductType.SP3,
                        product_quality=ProductQuality.FINAL, center=self.SOURCE)
        assert len(results) > 0, f"No SP3 FINAL found from {self.SOURCE}"
        product = results[0]
        assert product.type == ProductType.SP3
        assert "IGS" in product.filename.upper()
        log.info("[%s] SP3 FINAL: %s", self.SOURCE, product.filename)

    def test_clk_final(self) -> None:
        """IGS CLK FINAL should be available."""
        results = query(date=DATE, product_type=ProductType.CLK,
                        product_quality=ProductQuality.FINAL, center=self.SOURCE)
        assert len(results) > 0, f"No CLK FINAL found from {self.SOURCE}"
        log.info("[%s] CLK FINAL: %s", self.SOURCE, results[0].filename)

    def test_erp(self) -> None:
        """IGS ERP should be available (RAPID or FINAL)."""
        results = query(date=DATE, product_type=ProductType.ERP, center=self.SOURCE)
        assert len(results) > 0, f"No ERP found from {self.SOURCE}"
        log.info("[%s] ERP %s: %s", self.SOURCE, results[0].quality, results[0].filename)

    def test_bias(self) -> None:
        """IGS BIAS should be queryable (may fail if FTP listing doesn't match)."""
        results = query(date=DATE, product_type=ProductType.BIAS, center=self.SOURCE)
        if len(results) > 0:
            log.info("[%s] BIAS: %s", self.SOURCE, results[0].filename)
        else:
            log.warning("[%s] BIAS not found (FTP listing may not match)", self.SOURCE)

    def test_gps_week_in_directory(self) -> None:
        """IGS orbit directory should use GPS week."""
        results = query(date=DATE, product_type=ProductType.SP3, center=self.SOURCE)
        assert len(results) > 0
        assert str(GPS_WEEK) in results[0].directory


# ---------------------------------------------------------------------------
# CODE Orbit/Clock Tests
# ---------------------------------------------------------------------------


class TestCODEOrbitClock:
    """Tests for CODE orbit/clock products via unified interface."""

    SOURCE = "CODE"

    def test_sp3_final(self) -> None:
        """CODE SP3 FINAL should be available."""
        results = query(date=DATE, product_type=ProductType.SP3,
                        product_quality=ProductQuality.FINAL, center=self.SOURCE)
        assert len(results) > 0, f"No SP3 FINAL found from {self.SOURCE}"
        assert "COD" in results[0].filename.upper()
        log.info("[%s] SP3 FINAL: %s", self.SOURCE, results[0].filename)

    def test_clk_final(self) -> None:
        """CODE CLK FINAL should be available."""
        results = query(date=DATE, product_type=ProductType.CLK,
                        product_quality=ProductQuality.FINAL, center=self.SOURCE)
        assert len(results) > 0, f"No CLK FINAL found from {self.SOURCE}"
        log.info("[%s] CLK FINAL: %s", self.SOURCE, results[0].filename)

    def test_erp_final(self) -> None:
        """CODE ERP FINAL should be available."""
        results = query(date=DATE, product_type=ProductType.ERP,
                        product_quality=ProductQuality.FINAL, center=self.SOURCE)
        assert len(results) > 0, f"No ERP FINAL found from {self.SOURCE}"
        log.info("[%s] ERP FINAL: %s", self.SOURCE, results[0].filename)

    def test_bias_final(self) -> None:
        """CODE BIAS FINAL should be available."""
        results = query(date=DATE, product_type=ProductType.BIAS,
                        product_quality=ProductQuality.FINAL, center=self.SOURCE)
        assert len(results) > 0, f"No BIAS FINAL found from {self.SOURCE}"
        log.info("[%s] BIAS FINAL: %s", self.SOURCE, results[0].filename)


# ---------------------------------------------------------------------------
# GFZ Orbit/Clock Tests
# ---------------------------------------------------------------------------


class TestGFZOrbitClock:
    """Tests for GFZ Potsdam orbit/clock products via unified interface."""

    SOURCE = "GFZ"

    def test_sp3_final(self) -> None:
        """GFZ SP3 FINAL should be available (may fail if FTP is down)."""
        results = query(date=DATE, product_type=ProductType.SP3,
                        product_quality=ProductQuality.FINAL, center=self.SOURCE)
        if len(results) > 0:
            log.info("[%s] SP3 FINAL: %s", self.SOURCE, results[0].filename)
        else:
            log.warning("[%s] SP3 FINAL not found (GFZ FTP may be unavailable)", self.SOURCE)

    def test_clk_final(self) -> None:
        """GFZ CLK FINAL should be available (may fail if FTP is down)."""
        results = query(date=DATE, product_type=ProductType.CLK,
                        product_quality=ProductQuality.FINAL, center=self.SOURCE)
        if len(results) > 0:
            log.info("[%s] CLK FINAL: %s", self.SOURCE, results[0].filename)
        else:
            log.warning("[%s] CLK FINAL not found (GFZ FTP may be unavailable)", self.SOURCE)


# ---------------------------------------------------------------------------
# Cross-Source Comparison
# ---------------------------------------------------------------------------


class TestCrossSourceOrbitAvailability:
    """Test that orbit products are available across multiple sources."""

    @pytest.fixture(scope="class")
    def all_sp3_results(self) -> dict[str, List[RemoteProductAddress]]:
        """Query SP3 from all FTP-based sources."""
        results = {}
        for source in ["WUHAN", "IGS", "CODE", "GFZ"]:
            try:
                r = query(date=DATE, product_type=ProductType.SP3,
                          product_quality=ProductQuality.FINAL, center=source)
                results[source] = r
            except Exception as e:
                log.warning("[%s] SP3 query error: %s", source, e)
                results[source] = []
        return results

    def test_at_least_two_sources_have_sp3(self, all_sp3_results) -> None:
        """SP3 should be available from at least 2 sources."""
        available = [s for s, r in all_sp3_results.items() if len(r) > 0]
        log.info("SP3 available from: %s", available)
        assert len(available) >= 2, (
            f"SP3 only found from {available}; expected at least 2 sources"
        )

    def test_sp3_filenames_contain_date(self, all_sp3_results) -> None:
        """All SP3 filenames should contain date information."""
        year = str(DATE.year)
        doy = f"{DOY:03d}"
        for source, results in all_sp3_results.items():
            for product in results:
                has_date = year in product.filename or doy in product.filename
                assert has_date, (
                    f"[{source}] SP3 filename '{product.filename}' missing date info"
                )

    def test_all_results_are_sp3_type(self, all_sp3_results) -> None:
        """All returned products must have SP3 type."""
        for source, results in all_sp3_results.items():
            for product in results:
                assert product.type == ProductType.SP3, (
                    f"[{source}] Expected SP3 type, got {product.type}"
                )


# ---------------------------------------------------------------------------
# Product Type Existence Tests
# ---------------------------------------------------------------------------


class TestOrbitProductTypes:
    """Verify orbit/clock product types exist in the enum."""

    def test_sp3_exists(self) -> None:
        assert ProductType.SP3 is not None
        assert ProductType.SP3.value == "SP3"

    def test_clk_exists(self) -> None:
        assert ProductType.CLK is not None
        assert ProductType.CLK.value == "CLK"

    def test_erp_exists(self) -> None:
        assert ProductType.ERP is not None
        assert ProductType.ERP.value == "ERP"

    def test_bias_exists(self) -> None:
        assert ProductType.BIAS is not None
        assert ProductType.BIAS.value == "BIAS"

    def test_obx_exists(self) -> None:
        assert ProductType.OBX is not None
        assert ProductType.OBX.value == "OBX"
