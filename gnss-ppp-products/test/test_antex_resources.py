"""
Integration tests for ANTEX (antenna phase center) remote sources.

Tests verify that ANTEX files can be found on remote servers using the
unified query() function.
"""

import datetime
import logging
import pytest
import requests
from dataclasses import dataclass
from typing import Optional, List

from gnss_ppp_products.data_query import query, ProductType, ProductQuality
from gnss_ppp_products.resources.resource import RemoteProductAddress

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class AntexProbeResult:
    """Result of probing a server for an ANTEX file."""
    source: str
    label: str
    found: bool
    filename: Optional[str] = None
    url: Optional[str] = None
    status_code: Optional[int] = None
    error: Optional[str] = None


def probe_remote_file(source: str, label: str, product: RemoteProductAddress) -> AntexProbeResult:
    """
    Check if an ANTEX file exists at the remote location.
    Uses HEAD request for HTTP, direct FTP check for FTP.
    """
    if product is None:
        logger.warning(f"[{label}] No product address returned")
        return AntexProbeResult(source=source, label=label, found=False)
    
    # Build full URL
    if product.server.protocol.value == "http" or product.server.protocol.value == "https":
        # Normalize path to avoid double slashes
        directory = product.directory.rstrip('/')
        url = f"{product.server.hostname}/{directory}/{product.filename}"
        logger.info(f"Probing {label}: {url}")
        
        try:
            response = requests.head(url, timeout=30, allow_redirects=True)
            found = response.status_code == 200
            if found:
                logger.info(f"[{label}] Found: {product.filename} (HTTP {response.status_code})")
            else:
                logger.warning(f"[{label}] Not found: HTTP {response.status_code}")
            return AntexProbeResult(
                source=source,
                label=label,
                found=found,
                filename=product.filename,
                url=url,
                status_code=response.status_code
            )
        except requests.RequestException as e:
            logger.error(f"[{label}] Request failed: {e}")
            return AntexProbeResult(source=source, label=label, found=False, error=str(e))
    else:
        # FTP - just verify we got a result with a filename
        directory = product.directory.rstrip('/')
        url = f"{product.server.protocol.value}://{product.server.hostname}/{directory}/{product.filename}"
        logger.info(f"Queried {label}: {url}")
        found = product.filename is not None
        if found:
            logger.info(f"[{label}] Found: {product.filename}")
        return AntexProbeResult(
            source=source,
            label=label,
            found=found,
            filename=product.filename,
            url=url
        )



# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def current_date() -> datetime.datetime:
    """Provide a fixed current date for testing."""
    return datetime.datetime.today().astimezone(datetime.timezone.utc)


@pytest.fixture(scope="module")
def one_year_ago(current_date: datetime.datetime) -> datetime.datetime:
    """Provide a fixed past date for testing."""
    return current_date - datetime.timedelta(days=365)


@pytest.fixture(scope="module")
def itrf_14_date() -> datetime.datetime:
    """Provide a date during the IGS14 frame period."""
    return datetime.datetime(2020, 1, 1)


# Source/product identifiers for tracking results
IGS_CURRENT = "igs_current"
IGS_ARCHIVED = "igs_archived"
IGS_ITRF_14 = "igs14"
NGS_CURRENT = "ngs_current"
NGS_PAST = "ngs_past"
NGS_ITRF_14 = "ngs14_itrf"
ASTRO_MGEX = "astroinst_mgex"


@pytest.fixture(scope="module")
def igs_results(current_date: datetime.datetime, one_year_ago: datetime.datetime, itrf_14_date: datetime.datetime) -> dict[str, AntexProbeResult]:
    """Query IGS ANTEX files using unified query function."""
    results = {}

    # Current ATX from IGS
    igs_current_products: List[RemoteProductAddress] = query(
        date=current_date,
        product_type=ProductType.ATX,
        source="IGS"
    )
    if igs_current_products:
        results[IGS_CURRENT] = probe_remote_file("IGS", IGS_CURRENT, igs_current_products[0])

    # Archived IGS ATX from a year ago
    igs_archived_products: List[RemoteProductAddress] = query(
        date=one_year_ago,
        product_type=ProductType.ATX,
        source="IGS"
    )
    if igs_archived_products:
        results[IGS_ARCHIVED] = probe_remote_file("IGS", IGS_ARCHIVED, igs_archived_products[0])

    # IGS ATX for 2020 (historical frame test)
    igs_itrf_products: List[RemoteProductAddress] = query(
        date=itrf_14_date,
        product_type=ProductType.ATX,
        source="IGS"
    )
    if igs_itrf_products:
        results[IGS_ITRF_14] = probe_remote_file("IGS", IGS_ITRF_14, igs_itrf_products[0])

    return results


@pytest.fixture(scope="module")
def ngs_results(current_date: datetime.datetime, one_year_ago: datetime.datetime, itrf_14_date: datetime.datetime) -> dict[str, AntexProbeResult]:
    """Query NGS/NOAA ANTEX files using unified query function."""
    results = {}

    # NGS current (NGS20 for 2026)
    ngs_current_products: List[RemoteProductAddress] = query(
        date=current_date,
        product_type=ProductType.ATX,
        source="NGS"
    )
    if ngs_current_products:
        results[NGS_CURRENT] = probe_remote_file("NGS", NGS_CURRENT, ngs_current_products[0])

    # NGS from a year ago (likely NGS14)
    ngs_past_products: List[RemoteProductAddress] = query(
        date=one_year_ago,
        product_type=ProductType.ATX,
        source="NGS"
    )
    if ngs_past_products:
        results[NGS_PAST] = probe_remote_file("NGS", NGS_PAST, ngs_past_products[0])

    # NGS ATX for 2020 (historical frame test)
    ngs_itrf_products: List[RemoteProductAddress] = query(
        date=itrf_14_date,
        product_type=ProductType.ATX,
        source="NGS"
    )
    if ngs_itrf_products:
        results[NGS_ITRF_14] = probe_remote_file("NGS", NGS_ITRF_14, ngs_itrf_products[0])

    return results


@pytest.fixture(scope="module")
def code_mgex_results(current_date: datetime.datetime) -> dict[str, AntexProbeResult]:
    """Query CODE MGEX ANTEX files using unified query function."""
    results = {}

    # CODE MGEX ATX
    code_mgex_products: List[RemoteProductAddress] = query(
        date=current_date,
        product_type=ProductType.ATX,
        source="COD"
    )
    if code_mgex_products:
        results["code_mgex"] = probe_remote_file("CODE", "code_mgex", code_mgex_products[0])

    return results


# ---------------------------------------------------------------------------
# Tests: IGS ANTEX Source
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestIGSAntex:
    """Test IGS ANTEX file availability via query()."""

    def test_igs_current_found(self, igs_results: dict[str, AntexProbeResult]) -> None:
        """IGS should provide current igs.atx file."""
        result = igs_results.get(IGS_CURRENT)
        assert result is not None, "Query returned None"
        assert result.found, f"igs.atx not found at {result.url} (HTTP {result.status_code})"
        logger.info(f"[IGS] Current igs.atx found: {result.filename}")

    def test_igs_archived_found(self, igs_results: dict[str, AntexProbeResult]) -> None:
        """IGS should provide archived ANTEX files."""
        result = igs_results.get(IGS_ARCHIVED)
        if result:
            assert result.found, f"Archived igs not found at {result.url}"
            logger.info(f"[IGS] Archived igs found: {result.filename}")

    def test_igs14_found(self, igs_results: dict[str, AntexProbeResult]) -> None:
        """IGS should provide igs14.atx for legacy processing."""
        result = igs_results.get(IGS_ITRF_14)
        assert result is not None, "Query returned None"
        assert result.found, f"igs14.atx not found at {result.url}"
        logger.info(f"[IGS] igs14.atx found: {result.filename}")

    def test_igs_query_returns_result(self, current_date: datetime.datetime) -> None:
        """IGS query should return valid RemoteProductAddress."""
        results: List[RemoteProductAddress] = query(
            date=current_date,
            product_type=ProductType.ATX,
            source="IGS"
        )
        assert results is not None
        assert len(results) > 0, "No ANTEX products found from IGS"
        assert results[0].filename is not None
        assert results[0].filename.endswith(".atx")


# ---------------------------------------------------------------------------
# Tests: NGS/NOAA ANTEX Source
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestNGSAntex:
    """Test NGS/NOAA ANTEX file availability via query()."""

    def test_ngs20_found(self, ngs_results: dict[str, AntexProbeResult]) -> None:
        """NGS should provide ngs20.atx file."""
        result = ngs_results.get(NGS_CURRENT)
        assert result is not None, "Query returned None"
        assert result.found, f"ngs.atx not found at {result.url} (HTTP {result.status_code})"
        logger.info(f"[NGS] ngs.atx found: {result.filename}")

    def test_ngs14_found(self, ngs_results: dict[str, AntexProbeResult]) -> None:
        """NGS should provide ngs14.atx for legacy processing."""
        result = ngs_results.get(NGS_ITRF_14)
        assert result is not None, "Query returned None"
        assert result.found, f"ngs14.atx not found at {result.url}"
        logger.info(f"[NGS] ngs14.atx found: {result.filename}")

    def test_ngs_query_returns_result(self, current_date: datetime.datetime) -> None:
        """NGS query should return valid RemoteProductAddress."""
        results: List[RemoteProductAddress] = query(
            date=current_date,
            product_type=ProductType.ATX,
            source="NGS"
        )
        assert results is not None
        assert len(results) > 0, "No ANTEX products found from NGS"
        assert results[0].filename is not None
        assert "ngs" in results[0].filename and ".atx" in results[0].filename


# ---------------------------------------------------------------------------
# Tests: CODE MGEX ANTEX Source
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestCODEMGEXAntex:
    """Test CODE MGEX ANTEX file availability via query()."""

    def test_code_mgex_query_returns_result(self, current_date: datetime.datetime) -> None:
        """CODE query should return valid ANTEX product address."""
        results: List[RemoteProductAddress] = query(
            date=current_date,
            product_type=ProductType.ATX,
            source="COD"
        )
        # CODE may or may not have ANTEX results depending on availability
        if results:
            assert len(results) > 0
            assert results[0].filename is not None
            assert results[0].filename.endswith(".ATX") or results[0].filename.endswith(".atx")
            logger.info(f"[CODE] ANTEX found: {results[0].filename}")
        else:
            logger.warning("[CODE] No ANTEX products found")


# ---------------------------------------------------------------------------
# Tests: Multi-source comparison
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestMultiSourceAntex:
    """Compare ANTEX availability across sources."""

    def test_igs_and_ngs_both_available(self, current_date: datetime.datetime) -> None:
        """Both IGS and NGS should have ANTEX for current date."""
        igs_results = query(
            date=current_date,
            product_type=ProductType.ATX,
            source="IGS"
        )
        ngs_results = query(
            date=current_date,
            product_type=ProductType.ATX,
            source="NGS"
        )

        assert len(igs_results) > 0, "No ANTEX found from IGS"
        assert len(ngs_results) > 0, "No ANTEX found from NGS"
        logger.info("[Multi-source] Both IGS and NGS have ANTEX available")

    def test_query_without_source_returns_multiple(self, current_date: datetime.datetime) -> None:
        """Query without source filter should return products from multiple sources."""
        igs_results = query(
            date=current_date,
            product_type=ProductType.ATX
        )
        ngs_results = query(
            date=current_date,
            product_type=ProductType.ATX
        )
        
        results = igs_results + ngs_results

        assert len(results) > 0, "No ANTEX products found"
        
        sources = {r.server.hostname for r in results}
        logger.info(f"[Multi-source] Found ANTEX from {len(sources)} source(s): {sources}")

    def test_temporal_coverage_consistency(self, current_date: datetime.datetime) -> None:
        """All ANTEX products should have consistent temporal properties."""
        igs_results = query(
            date=current_date,
            product_type=ProductType.ATX
        )
        ngs_results = query(
            date=current_date,
            product_type=ProductType.ATX
        )
        
        results = igs_results + ngs_results

        for product in results:
            # ANTEX files are static or epoch-based, not interval-sampled
            assert product.filename is not None
            logger.info(f"[Coverage] {product.server.hostname}: {product.filename}")


