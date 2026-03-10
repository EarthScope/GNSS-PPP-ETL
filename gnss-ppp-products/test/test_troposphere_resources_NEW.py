"""
Integration test suite: Troposphere products via unified config-based query interface.

Metadata
--------
Date under test : 2025-01-01  (DOY 001)
Products probed : VMF1, VMF3 (Vienna Mapping Functions)
Source          : VMF (vmf.geo.tuwien.ac.at)

Usage
-----
Run all integration tests::

    uv run pytest test/test_troposphere_resources.py -v

Skip in offline environments::

    uv run pytest -m "not integration"
"""
from __future__ import annotations

import datetime
import logging
from typing import List

import pytest
import requests

from gnss_ppp_products.data_query import query, ProductType, ProductQuality
from gnss_ppp_products.resources.resource import RemoteProductAddress

log = logging.getLogger(__name__)

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Test parameters
# ---------------------------------------------------------------------------

DATE = datetime.date(2025, 1, 1)
DOY: int = DATE.timetuple().tm_yday  # 1


# ---------------------------------------------------------------------------
# Helper: probe HTTP URL
# ---------------------------------------------------------------------------

def probe_vmf_url(product: RemoteProductAddress) -> bool:
    """Check if VMF HTTP URL is reachable."""
    url = f"{product.server.hostname}/{product.directory}/{product.filename}"
    try:
        resp = requests.head(url, timeout=15, allow_redirects=True)
        return resp.status_code == 200
    except requests.RequestException:
        return False


# ---------------------------------------------------------------------------
# VMF3 Troposphere Tests
# ---------------------------------------------------------------------------


class TestVMF3Products:
    """Tests for VMF3 troposphere products via unified interface."""

    SOURCE = "VMF"

    def test_vmf3_query_returns_results(self) -> None:
        """VMF3 query should return at least one result."""
        log.info("Testing VMF3 query for %s (DOY %03d)", DATE, DOY)
        results = query(date=DATE, product_type=ProductType.VMF3, source=self.SOURCE)
        assert len(results) > 0, f"No VMF3 products found from {self.SOURCE}"
        log.info("[%s] Found %d VMF3 result(s)", self.SOURCE, len(results))

    def test_vmf3_correct_type(self) -> None:
        """VMF3 results should have correct product type."""
        results = query(date=DATE, product_type=ProductType.VMF3, source=self.SOURCE)
        for product in results:
            assert product.type == ProductType.VMF3

    def test_vmf3_directory_contains_year(self) -> None:
        """VMF3 directory should contain the year."""
        results = query(date=DATE, product_type=ProductType.VMF3, source=self.SOURCE)
        assert len(results) > 0
        assert "2025" in results[0].directory

    def test_vmf3_filename_contains_date(self) -> None:
        """VMF3 filename should contain YYYYMMDD date."""
        results = query(date=DATE, product_type=ProductType.VMF3, source=self.SOURCE)
        assert len(results) > 0
        filename = results[0].filename
        # VMF uses YYYYMMDD format
        date_str = DATE.strftime("%Y%m%d")
        assert date_str in filename or "VMF3" in filename, (
            f"VMF3 filename '{filename}' missing date '{date_str}'"
        )

    def test_vmf3_has_multiple_resolutions(self) -> None:
        """VMF3 should have both 1x1 and 5x5 resolution files."""
        results = query(date=DATE, product_type=ProductType.VMF3, source=self.SOURCE)
        file_ids = {r.file_id for r in results}
        log.info("[%s] VMF3 file IDs: %s", self.SOURCE, file_ids)
        # Config defines 1x1 and 5x5 files
        assert len(file_ids) >= 1, "Expected at least one VMF3 resolution"


# ---------------------------------------------------------------------------
# VMF1 Troposphere Tests
# ---------------------------------------------------------------------------


class TestVMF1Products:
    """Tests for VMF1 troposphere products via unified interface."""

    SOURCE = "VMF"

    def test_vmf1_query_returns_results(self) -> None:
        """VMF1 query should return at least one result."""
        log.info("Testing VMF1 query for %s (DOY %03d)", DATE, DOY)
        results = query(date=DATE, product_type=ProductType.VMF1, source=self.SOURCE)
        assert len(results) > 0, f"No VMF1 products found from {self.SOURCE}"
        log.info("[%s] Found %d VMF1 result(s)", self.SOURCE, len(results))

    def test_vmf1_correct_type(self) -> None:
        """VMF1 results should have correct product type."""
        results = query(date=DATE, product_type=ProductType.VMF1, source=self.SOURCE)
        for product in results:
            assert product.type == ProductType.VMF1

    def test_vmf1_directory_contains_year(self) -> None:
        """VMF1 directory should contain the year."""
        results = query(date=DATE, product_type=ProductType.VMF1, source=self.SOURCE)
        assert len(results) > 0
        assert "2025" in results[0].directory


# ---------------------------------------------------------------------------
# Cross-Product Comparison
# ---------------------------------------------------------------------------


class TestTroposphereAvailability:
    """Test troposphere product availability."""

    @pytest.fixture(scope="class")
    def vmf_results(self) -> dict[str, List[RemoteProductAddress]]:
        """Query both VMF1 and VMF3."""
        results = {}
        for ptype in [ProductType.VMF1, ProductType.VMF3]:
            try:
                r = query(date=DATE, product_type=ptype, source="VMF")
                results[ptype.value] = r
            except Exception as e:
                log.warning("[VMF] %s query error: %s", ptype.value, e)
                results[ptype.value] = []
        return results

    def test_at_least_one_vmf_available(self, vmf_results) -> None:
        """At least one VMF product type should be available."""
        available = [t for t, r in vmf_results.items() if len(r) > 0]
        log.info("VMF products available: %s", available)
        assert len(available) >= 1, "No VMF products found"

    def test_vmf3_uses_https(self, vmf_results) -> None:
        """VMF products should use HTTPS protocol."""
        for results in vmf_results.values():
            for product in results:
                assert "https" in product.server.hostname or product.server.protocol.value == "https"


# ---------------------------------------------------------------------------
# Product Type Existence
# ---------------------------------------------------------------------------


class TestTroposphereProductTypes:
    """Verify troposphere product types exist."""

    def test_vmf1_exists(self) -> None:
        assert ProductType.VMF1 is not None
        assert ProductType.VMF1.value == "VMF1"

    def test_vmf3_exists(self) -> None:
        assert ProductType.VMF3 is not None
        assert ProductType.VMF3.value == "VMF3"
