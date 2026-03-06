"""
Integration test suite: Orography products from HTTP sources.

Metadata
--------
Products probed : Orography grid files (1x1, 5x5)
Servers         : VMF (vmf.geo.tuwien.ac.at)

Usage
-----
Run all integration tests::

    uv run pytest test/test_orography_resources.py -v

Skip in offline environments::

    uv run pytest -m "not integration"
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import pytest

from gnss_ppp_products.resources.orography_resources import (
    OrographyGridResolution,
    OrographyFileResult,
    VMFOrographyHTTPSource,
)
from gnss_ppp_products.resources.base import DownloadProtocol

log = logging.getLogger(__name__)

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Test parameters
# ---------------------------------------------------------------------------

RESOLUTIONS: list[str] = ["1x1", "5x5"]


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------


@dataclass
class OrographyProbeResult:
    """Outcome of querying an orography product."""

    resolution: str
    file_result: Optional[OrographyFileResult] = None
    error: Optional[str] = None

    @property
    def found(self) -> bool:
        return self.file_result is not None

    @property
    def filename(self) -> str:
        return self.file_result.filename if self.file_result else "not found"

    @property
    def full_url(self) -> str:
        return self.file_result.url if self.file_result else "—"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _print_summary(title: str, results: list[OrographyProbeResult]) -> None:
    """Print formatted summary table."""
    log.info("")
    log.info("=" * 80)
    log.info(f" {title}")
    log.info("=" * 80)
    
    for result in results:
        status = "✓ FOUND" if result.found else "✗ NOT FOUND"
        log.info(f"  Resolution: {result.resolution} | {status}")
        if result.found:
            log.info(f"      → {result.filename}")
            log.info(f"      URL: {result.full_url}")
        if result.error:
            log.info(f"      ERROR: {result.error}")
    
    log.info("=" * 80)


# ---------------------------------------------------------------------------
# VMF Orography Tests
# ---------------------------------------------------------------------------


class TestVMFOrographyHTTPSource:
    """Tests for VMF orography file queries from vmf.geo.tuwien.ac.at."""

    @pytest.fixture(scope="class")
    def source(self) -> VMFOrographyHTTPSource:
        return VMFOrographyHTTPSource()

    def test_query_1x1_resolution(self, source: VMFOrographyHTTPSource) -> None:
        """Test querying orography file with 1x1 resolution."""
        log.info("Testing VMF orography query for 1x1 resolution")
        
        result = source.query(resolution="1x1")
        
        assert result is not None, "Expected orography file for 1x1 resolution, got None"
        assert result.filename == "orography_ell_1x1"
        assert result.resolution == OrographyGridResolution.ONE_BY_ONE
        assert result.protocol == DownloadProtocol.HTTPS
        assert result.server == "https://vmf.geo.tuwien.ac.at"
        
        log.info("  Found: %s", result.filename)
        log.info("  URL: %s", result.url)

    def test_query_5x5_resolution(self, source: VMFOrographyHTTPSource) -> None:
        """Test querying orography file with 5x5 resolution."""
        log.info("Testing VMF orography query for 5x5 resolution")
        
        result = source.query(resolution="5x5")
        
        assert result is not None, "Expected orography file for 5x5 resolution, got None"
        assert result.filename == "orography_ell_5x5"
        assert result.resolution == OrographyGridResolution.FIVE_BY_FIVE
        assert result.protocol == DownloadProtocol.HTTPS
        
        log.info("  Found: %s", result.filename)
        log.info("  URL: %s", result.url)

    def test_invalid_resolution_raises(self, source: VMFOrographyHTTPSource) -> None:
        """Test that invalid resolution raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported grid resolution"):
            source.query(resolution="2x2")  # type: ignore

    def test_url_construction(self, source: VMFOrographyHTTPSource) -> None:
        """Test that URLs are correctly constructed."""
        result = source.query(resolution="1x1")
        
        assert result is not None
        expected_url = "https://vmf.geo.tuwien.ac.at/station_coord_files/orography_ell_1x1"
        assert result.url == expected_url

    def test_directory_path(self, source: VMFOrographyHTTPSource) -> None:
        """Test that directory paths are correctly set."""
        result = source.query(resolution="5x5")
        
        assert result is not None
        assert result.directory == "station_coord_files"


# ---------------------------------------------------------------------------
# Summary test
# ---------------------------------------------------------------------------


class TestOrographySummary:
    """Summary test that probes all orography resolutions."""

    def test_all_resolutions(self) -> None:
        """Probe all available orography resolutions and print summary."""
        source = VMFOrographyHTTPSource()
        results: list[OrographyProbeResult] = []
        
        for resolution in RESOLUTIONS:
            try:
                file_result = source.query(resolution=resolution)  # type: ignore
                results.append(OrographyProbeResult(
                    resolution=resolution,
                    file_result=file_result,
                ))
            except Exception as e:
                results.append(OrographyProbeResult(
                    resolution=resolution,
                    error=str(e),
                ))
        
        _print_summary("VMF Orography Products Summary", results)
        
        # At least one resolution should be available
        found_count = sum(1 for r in results if r.found)
        assert found_count >= 1, "Expected at least one orography resolution to be available"
