"""
Integration test suite: Orography products via unified config-based query interface.

Metadata
--------
Products probed : OROGRAPHY (terrain height grids)
Source          : VMF (vmf.geo.tuwien.ac.at)

Usage
-----
Run all integration tests::

    uv run pytest test/test_orography_resources.py -v

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

SOURCE = "VMF"
# Orography is static (not date-dependent) but query() requires a date
DUMMY_DATE = datetime.date(2025, 1, 1)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def probe_orography_url(product: RemoteProductAddress) -> bool:
    """Check if an orography HTTP URL is reachable."""
    url = f"{product.server.hostname}/{product.directory}/{product.filename}"
    try:
        resp = requests.head(url, timeout=15, allow_redirects=True)
        return resp.status_code == 200
    except requests.RequestException:
        return False


# ---------------------------------------------------------------------------
# VMF Orography Tests
# ---------------------------------------------------------------------------


class TestVMFOrography:
    """Tests for VMF orography products via unified interface."""

    def test_orography_query_returns_results(self) -> None:
        """Orography query should return at least one result."""
        log.info("Testing VMF orography query")
        results = query(date=DUMMY_DATE, product_type=ProductType.OROGRAPHY, center=SOURCE)
        assert len(results) > 0, f"No OROGRAPHY products found from {SOURCE}"
        log.info("[%s] Found %d orography result(s)", SOURCE, len(results))
        for r in results:
            log.info("  File ID: %s, Filename: %s", r.file_id, r.filename)

    def test_orography_correct_type(self) -> None:
        """Results should have OROGRAPHY product type."""
        results = query(date=DUMMY_DATE, product_type=ProductType.OROGRAPHY, center=SOURCE)
        for product in results:
            assert product.type == ProductType.OROGRAPHY

    def test_orography_has_1x1_resolution(self) -> None:
        """Orography should include 1x1 resolution file."""
        results = query(date=DUMMY_DATE, product_type=ProductType.OROGRAPHY, center=SOURCE)
        file_ids = {r.file_id for r in results}
        assert "1x1" in file_ids, f"No 1x1 resolution found; got file_ids: {file_ids}"

    def test_orography_has_5x5_resolution(self) -> None:
        """Orography should include 5x5 resolution file."""
        results = query(date=DUMMY_DATE, product_type=ProductType.OROGRAPHY, center=SOURCE)
        file_ids = {r.file_id for r in results}
        assert "5x5" in file_ids, f"No 5x5 resolution found; got file_ids: {file_ids}"

    def test_orography_filenames(self) -> None:
        """Orography filenames should contain 'orography_ell'."""
        results = query(date=DUMMY_DATE, product_type=ProductType.OROGRAPHY, center=SOURCE)
        for product in results:
            assert "orography_ell" in product.filename, (
                f"Unexpected orography filename: {product.filename}"
            )

    def test_orography_directory(self) -> None:
        """Orography files should be in station_files/GRID/ directory."""
        results = query(date=DUMMY_DATE, product_type=ProductType.OROGRAPHY, center=SOURCE)
        assert len(results) > 0
        for product in results:
            assert "station_files" in product.directory or "GRID" in product.directory

    def test_orography_uses_https(self) -> None:
        """Orography server should use HTTPS."""
        results = query(date=DUMMY_DATE, product_type=ProductType.OROGRAPHY, center=SOURCE)
        assert len(results) > 0
        for product in results:
            assert "https" in product.server.hostname or product.server.protocol.value == "https"


# ---------------------------------------------------------------------------
# Product Type Existence
# ---------------------------------------------------------------------------


class TestOrographyProductType:
    """Verify orography product type exists."""

    def test_orography_exists(self) -> None:
        assert ProductType.OROGRAPHY is not None
        assert ProductType.OROGRAPHY.value == "OROGRAPHY"
