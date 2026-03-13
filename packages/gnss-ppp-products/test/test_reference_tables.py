"""
Integration tests for reference table FTP sources.

Tests verify that leap second and satellite parameter files
can be found on remote FTP servers.
"""

import logging
import pytest
from urllib.parse import urlparse
from dataclasses import dataclass
from typing import Optional

from gnss_ppp_products.resources import (
    WuhanProductTableFTPSource,
    CDDISProductTableFTPSource,
)
from gnss_ppp_products.resources.remote.utils import ftp_list_directory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TableProbeResult:
    """Result of probing an FTP server for a reference table file."""
    label: str
    url: str
    found: bool
    filename: Optional[str] = None


def probe_ftp_file(label: str, url: str, use_tls: bool = False) -> TableProbeResult:
    """
    Check if a file exists at the given FTP URL.
    
    Parses the URL, lists the directory, and checks if the file is present.
    """
    parsed = urlparse(url)
    ftpserver = f"ftp://{parsed.netloc}"
    path_parts = parsed.path.rsplit("/", 1)
    directory = path_parts[0].lstrip("/")
    filename = path_parts[1] if len(path_parts) > 1 else ""
    
    logger.info(f"Probing {label}: {ftpserver} / {directory} / {filename}")
    
    listing = ftp_list_directory(ftpserver, directory, timeout=60, use_tls=use_tls)
    
    if not listing:
        logger.warning(f"[{label}] Could not list directory: {directory}")
        return TableProbeResult(label=label, url=url, found=False)
    
    if filename in listing:
        logger.info(f"[{label}] Found: {filename}")
        return TableProbeResult(label=label, url=url, found=True, filename=filename)
    
    logger.warning(f"[{label}] File not found: {filename}")
    return TableProbeResult(label=label, url=url, found=False)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def wuhan_source() -> WuhanProductTableFTPSource:
    return WuhanProductTableFTPSource()


@pytest.fixture(scope="module")
def cddis_source() -> CDDISProductTableFTPSource:
    return CDDISProductTableFTPSource()


@pytest.fixture(scope="module")
def wuhan_results(wuhan_source: WuhanProductTableFTPSource) -> dict[str, TableProbeResult]:
    """Probe Wuhan FTP server for all reference table files."""
    results = {}
    
    # Leap seconds
    results["leap_sec"] = probe_ftp_file(
        "Wuhan leap.sec",
        wuhan_source.leap_sec(),
        use_tls=False
    )
    
    # Satellite parameters
    results["sat_parameters"] = probe_ftp_file(
        "Wuhan sat_parameters",
        wuhan_source.sat_parameters(),
        use_tls=False
    )
    
    return results


@pytest.fixture(scope="module")
def cddis_results(cddis_source: CDDISProductTableFTPSource) -> dict[str, TableProbeResult]:
    """Probe CDDIS FTP server for all reference table files (requires TLS)."""
    results = {}
    
    # Leap seconds
    results["leap_sec"] = probe_ftp_file(
        "CDDIS leapsec.dat",
        cddis_source.leap_sec(),
        use_tls=True  # CDDIS requires TLS
    )
    
    return results


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestWuhanReferenceTables:
    """Test Wuhan FTP server reference table availability."""

    def test_leap_sec_found(self, wuhan_results: dict[str, TableProbeResult]) -> None:
        """Wuhan should provide leap second file."""
        result = wuhan_results["leap_sec"]
        assert result.found, f"Leap second file not found at {result.url}"
        logger.info(f"[Wuhan] leap.sec found: {result.filename}")

    def test_sat_parameters_found(self, wuhan_results: dict[str, TableProbeResult]) -> None:
        """Wuhan should provide satellite parameters file."""
        result = wuhan_results["sat_parameters"]
        assert result.found, f"Satellite parameters file not found at {result.url}"
        logger.info(f"[Wuhan] sat_parameters found: {result.filename}")

    def test_urls_are_valid(self, wuhan_source: WuhanProductTableFTPSource) -> None:
        """URLs should be properly formatted."""
        leap_url = wuhan_source.leap_sec()
        sat_url = wuhan_source.sat_parameters()
        
        assert leap_url.startswith("ftp://"), f"Invalid leap_sec URL: {leap_url}"
        assert sat_url.startswith("ftp://"), f"Invalid sat_parameters URL: {sat_url}"
        assert "leap.sec" in leap_url
        assert "sat_parameters" in sat_url


@pytest.mark.integration
class TestCDDISReferenceTables:
    """Test CDDIS FTP server reference table availability (requires TLS)."""

    def test_leap_sec_found(self, cddis_results: dict[str, TableProbeResult]) -> None:
        """CDDIS should provide leap second file."""
        result = cddis_results["leap_sec"]
        assert result.found, f"Leap second file not found at {result.url}"
        logger.info(f"[CDDIS] leapsec.dat found: {result.filename}")

    def test_url_is_valid(self, cddis_source: CDDISProductTableFTPSource) -> None:
        """URL should be properly formatted."""
        leap_url = cddis_source.leap_sec()
        
        assert leap_url.startswith("ftp://"), f"Invalid leap_sec URL: {leap_url}"
        assert "leapsec" in leap_url or "leap" in leap_url


# ---------------------------------------------------------------------------
# Tests for standardized .query() interface
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestQueryInterface:
    """Test the standardized .query() interface for reference tables."""

    def test_wuhan_query_leap_seconds(self, wuhan_source: WuhanProductTableFTPSource) -> None:
        """Wuhan query() should return leap_seconds result."""
        result = wuhan_source.query(product="leap_seconds")
        
        assert result is not None
        assert result.filename == "leap.sec"
        assert "igs.gnsswhu.cn" in result.server
        assert result.table_type.value == "leap_seconds"
        logger.info(f"[Wuhan] query('leap_seconds') URL: {result.url}")

    def test_wuhan_query_sat_parameters(self, wuhan_source: WuhanProductTableFTPSource) -> None:
        """Wuhan query() should return sat_parameters result."""
        result = wuhan_source.query(product="sat_parameters")
        
        assert result is not None
        assert result.filename == "sat_parameters"
        assert result.table_type.value == "sat_parameters"
        logger.info(f"[Wuhan] query('sat_parameters') URL: {result.url}")

    def test_cddis_query_leap_seconds(self, cddis_source: CDDISProductTableFTPSource) -> None:
        """CDDIS query() should return leap_seconds result."""
        result = cddis_source.query(product="leap_seconds")
        
        assert result is not None
        assert result.filename == "leapsec.dat"
        assert "cddis" in result.server
        assert result.table_type.value == "leap_seconds"
        logger.info(f"[CDDIS] query('leap_seconds') URL: {result.url}")

    def test_wuhan_invalid_product_raises(self, wuhan_source: WuhanProductTableFTPSource) -> None:
        """Invalid product should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown product type"):
            wuhan_source.query(product="invalid_product")  # type: ignore

    def test_cddis_invalid_product_raises(self, cddis_source: CDDISProductTableFTPSource) -> None:
        """Invalid product should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown product type"):
            cddis_source.query(product="invalid_product")  # type: ignore
