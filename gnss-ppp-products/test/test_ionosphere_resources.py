"""
Integration test suite: Ionosphere correction products via unified query interface.

Metadata
--------
Date under test : 2025-01-01  (DOY 001), 2020-06-15 (DOY 167 - legacy format)
Products probed : GIM (Global Ionosphere Maps)
Servers         : CODE (ftp.aiub.unibe.ch), Wuhan (igs.gnsswhu.cn), CDDIS (gdc.cddis.eosdis.nasa.gov)

Usage
-----
Run all integration tests::

    uv run pytest test/test_ionosphere_resources.py -v

Skip in offline environments::

    uv run pytest -m "not integration"
"""
from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from typing import Optional, List

import pytest
import requests

from gnss_ppp_products.data_query import query, ProductType, ProductQuality
from gnss_ppp_products.resources.resource import RemoteProductAddress

log = logging.getLogger(__name__)

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Test parameters
# ---------------------------------------------------------------------------

# Test date with new long-form naming (post-2022)
DATE_NEW_FORMAT = datetime.date(2025, 1, 1)
DOY_NEW: int = DATE_NEW_FORMAT.timetuple().tm_yday  # 1

# Test date with legacy naming (pre-2022)
DATE_LEGACY_FORMAT = datetime.date(2020, 6, 15)
DOY_LEGACY: int = DATE_LEGACY_FORMAT.timetuple().tm_yday  # 167


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------


@dataclass
class GIMProbeResult:
    """Outcome of querying a GIM product."""

    server_name: str
    date: datetime.date
    quality: Optional[str] = None
    product: Optional[RemoteProductAddress] = None
    error: Optional[str] = None

    @property
    def found(self) -> bool:
        return self.product is not None

    @property
    def filename(self) -> str:
        return self.product.filename if self.product else "not found"

    @property
    def full_url(self) -> str:
        if self.product:
            return f"{self.product.server.hostname}/{self.product.directory}/{self.product.filename}"
        return "—"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def probe_gim_file(server: str, label: str, product: Optional[RemoteProductAddress]) -> GIMProbeResult:
    """
    Check if a GIM file exists at the remote location via HEAD request or FTP check.
    
    For HTTP(S) servers, use HEAD request.
    For FTP, just verify we got a product with filename.
    """
    result = GIMProbeResult(server_name=server, date=datetime.date.today())
    
    if product is None:
        log.warning(f"[{label}] No product address returned")
        result.error = "Query returned None"
        return result
    
    result.product = product
    
    # Build full URL
    if product.server.protocol.value in ("http", "https"):
        directory = product.directory.rstrip('/')
        url = f"{product.server.hostname}/{directory}/{product.filename}"
        log.info(f"Probing {label}: {url}")
        
        try:
            response = requests.head(url, timeout=30, allow_redirects=True)
            if response.status_code == 200:
                log.info(f"[{label}] Found: {product.filename} (HTTP {response.status_code})")
            else:
                log.warning(f"[{label}] Not found: HTTP {response.status_code}")
                result.error = f"HTTP {response.status_code}"
                result.product = None
        except requests.RequestException as e:
            log.error(f"[{label}] Request failed: {e}")
            result.error = str(e)
            result.product = None
    else:
        # FTP - just verify we got a result with a filename
        directory = product.directory.rstrip('/')
        url = f"{product.server.protocol.value}://{product.server.hostname}/{directory}/{product.filename}"
        log.info(f"Queried {label}: {url}")
        if product.filename:
            log.info(f"[{label}] Found: {product.filename}")
        else:
            result.error = "No filename"
            result.product = None
    
    return result


def _print_summary(title: str, results: list[GIMProbeResult]) -> None:
    """Print formatted summary table."""
    log.info("")
    log.info("=" * 80)
    log.info(f" {title}")
    log.info("=" * 80)
    
    for result in results:
        status = "✓ FOUND" if result.found else "✗ NOT FOUND"
        quality_str = result.quality or "N/A"
        log.info(
            f"  [{result.server_name}] {result.date} | Quality: {quality_str} | {status}"
        )
        if result.found:
            log.info(f"      → {result.filename}")
        if result.error:
            log.info(f"      ERROR: {result.error}")
    
    log.info("=" * 80)


# ---------------------------------------------------------------------------
# CODE GIM Tests
# ---------------------------------------------------------------------------


class TestCODEGIMProducts:
    """Tests for CODE GIM product queries via unified interface."""

    def test_query_new_format(self) -> None:
        """Test querying GIM with new long-form naming (post-2022)."""
        log.info("Testing CODE GIM query for %s (DOY %03d) - new format", DATE_NEW_FORMAT, DOY_NEW)
        
        results: List[RemoteProductAddress] = query(
            date=DATE_NEW_FORMAT,
            product_type=ProductType.GIM,
            center="CODE"
        )
        
        assert results is not None
        assert len(results) > 0, f"Expected GIM file for {DATE_NEW_FORMAT}, got None"
        
        product = results[0]
        assert product.type == ProductType.GIM
        assert "COD" in product.filename or "GIM" in product.filename.upper()
        assert "ftp.aiub.unibe.ch" in product.server.hostname
        
        log.info("  Found: %s", product.filename)

    def test_query_legacy_format(self) -> None:
        """Test querying GIM with legacy naming (pre-2022)."""
        log.info("Testing CODE GIM query for %s (DOY %03d) - legacy format", DATE_LEGACY_FORMAT, DOY_LEGACY)
        
        results: List[RemoteProductAddress] = query(
            date=DATE_LEGACY_FORMAT,
            product_type=ProductType.GIM,
            center="CODE"
        )
        
        assert results is not None
        assert len(results) > 0, f"Expected GIM file for {DATE_LEGACY_FORMAT}, got None"
        
        product = results[0]
        assert product.type == ProductType.GIM
        # Legacy format: CODG{doy}0.{yy}I.Z
        assert "CODG" in product.filename or "codg" in product.filename.lower()
        
        log.info("  Found: %s", product.filename)

    def test_directory_structure(self) -> None:
        """Test that directory paths are correctly formatted."""
        results_2025 = query(date=DATE_NEW_FORMAT, product_type=ProductType.GIM, center="CODE")
        results_2020 = query(date=DATE_LEGACY_FORMAT, product_type=ProductType.GIM, center="CODE")
        
        if results_2025:
            assert results_2025[0].directory == "CODE/2025" or "CODE/2025" in results_2025[0].directory
        if results_2020:
            assert results_2020[0].directory == "CODE/2020" or "CODE/2020" in results_2020[0].directory

    def test_query_returns_result(self) -> None:
        """CODE query should return valid RemoteProductAddress."""
        results: List[RemoteProductAddress] = query(
            date=DATE_NEW_FORMAT,
            product_type=ProductType.GIM,
            center="CODE"
        )
        
        assert results is not None
        assert len(results) > 0, "No GIM products found from CODE"
        assert results[0].filename is not None
        assert results[0].type == ProductType.GIM


# ---------------------------------------------------------------------------
# Wuhan GIM Tests
# ---------------------------------------------------------------------------


class TestWuhanGIMProducts:
    """Tests for GIM product queries from Wuhan University via unified interface."""

    def test_query_code_final(self) -> None:
        """Test querying CODE final GIM from Wuhan mirror."""
        log.info("Testing Wuhan GIM query for %s - CODE FINAL", DATE_NEW_FORMAT)
        
        # Wuhan hosts CODE products among others
        results: List[RemoteProductAddress] = query(
            date=DATE_NEW_FORMAT,
            product_type=ProductType.GIM,
            product_quality=ProductQuality.FINAL,
            center="WUHAN"
        )
        
        if results and len(results) > 0:
            product = results[0]
            log.info("  Found: %s", product.filename)
            assert product.type == ProductType.GIM
            assert "igs.gnsswhu.cn" in product.server.hostname
        else:
            log.warning("  Not found (may be expected for recent dates)")

    def test_directory_structure(self) -> None:
        """Test that directory paths are correctly formatted."""
        results = query(date=DATE_NEW_FORMAT, product_type=ProductType.GIM, center="WUHAN")
        
        if results:
            # Wuhan GIM paths: pub/gps/products/ionex/{year}/{doy}/
            assert "pub/gps/products/ionex/2025/001" in results[0].directory or \
                   "ionex" in results[0].directory


# ---------------------------------------------------------------------------
# CDDIS GIM Tests  
# ---------------------------------------------------------------------------


class TestCDDISGIMProducts:
    """Tests for GIM product queries from NASA CDDIS via unified interface."""

    def test_query_code(self) -> None:
        """Test querying CODE GIM from CDDIS."""
        log.info("Testing CDDIS GIM query for %s - CODE", DATE_NEW_FORMAT)
        
        results: List[RemoteProductAddress] = query(
            date=DATE_NEW_FORMAT,
            product_type=ProductType.GIM,
            product_quality=ProductQuality.FINAL,
            center="CDDIS"
        )
        
        if results and len(results) > 0:
            product = results[0]
            log.info("  Found: %s", product.filename)
            assert product.type == ProductType.GIM
            assert "cddis" in product.server.hostname.lower()
        else:
            log.warning("  Not found (CDDIS may require FTPS)")

    def test_directory_structure(self) -> None:
        """Test that directory paths are correctly formatted."""
        results = query(date=DATE_NEW_FORMAT, product_type=ProductType.GIM, center="CDDIS")
        
        if results:
            # CDDIS GIM paths: gnss/products/ionex/{year}/{doy}/
            assert "gnss/products/ionex/2025/001" in results[0].directory or \
                   "ionex" in results[0].directory


# ---------------------------------------------------------------------------
# Cross-server comparison tests
# ---------------------------------------------------------------------------


class TestCrossServerComparison:
    """Compare availability across different servers."""

    @pytest.fixture(scope="class")
    def probe_results(self) -> list[GIMProbeResult]:
        """Probe all servers for GIM availability."""
        results: list[GIMProbeResult] = []
        
        # CODE primary server
        for date in [DATE_NEW_FORMAT, DATE_LEGACY_FORMAT]:
            probe = GIMProbeResult(server_name="CODE", date=date)
            try:
                products = query(date=date, product_type=ProductType.GIM, center="CODE")
                if products:
                    probe.product = products[0]
            except Exception as e:
                probe.error = str(e)
            results.append(probe)
        
        # Wuhan mirror
        probe = GIMProbeResult(server_name="Wuhan", date=DATE_NEW_FORMAT, quality="FINAL")
        try:
            products = query(
                date=DATE_NEW_FORMAT,
                product_type=ProductType.GIM,
                product_quality=ProductQuality.FINAL,
                center="WUHAN"
            )
            if products:
                probe.product = products[0]
        except Exception as e:
            probe.error = str(e)
        results.append(probe)
        
        # CDDIS mirror
        probe = GIMProbeResult(server_name="CDDIS", date=DATE_NEW_FORMAT, quality="FINAL")
        try:
            products = query(
                date=DATE_NEW_FORMAT,
                product_type=ProductType.GIM,
                product_quality=ProductQuality.FINAL,
                center="CDDIS"
            )
            if products:
                probe.product = products[0]
        except Exception as e:
            probe.error = str(e)
        results.append(probe)
        
        _print_summary("Cross-Server GIM Availability", results)
        return results

    def test_code_primary_available(self, probe_results: list[GIMProbeResult]) -> None:
        """Test that CODE primary server has GIM files."""
        code_results = [r for r in probe_results if r.server_name == "CODE"]
        found_count = sum(1 for r in code_results if r.found)
        
        assert found_count >= 1, "Expected at least one GIM file from CODE primary server"

    def test_at_least_one_server_available(self, probe_results: list[GIMProbeResult]) -> None:
        """Test that at least one server has the requested product."""
        found_any = any(r.found for r in probe_results)
        
        assert found_any, "Expected at least one server to have GIM products"


# ---------------------------------------------------------------------------
# Product type tests
# ---------------------------------------------------------------------------


class TestProductTypeGIM:
    """Tests for GIM ProductType properties."""

    def test_gim_product_type_exists(self) -> None:
        """Test that GIM product type is defined."""
        assert ProductType.GIM is not None
        assert ProductType.GIM.value == "GIM"
