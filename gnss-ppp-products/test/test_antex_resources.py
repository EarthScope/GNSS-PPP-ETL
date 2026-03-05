"""
Integration tests for ANTEX (antenna phase center) HTTP sources.

Tests verify that ANTEX files can be found on remote servers via HTTP.
"""

import datetime
import logging
import pytest
import requests
from dataclasses import dataclass
from typing import Optional

from gnss_ppp_products.resources import (
    IGSAntexReferenceFrameType,
    AntexFileResult,
    IGSAntexHTTPSource,
    NGSNOAAAntexHTTPSource,
    determine_frame
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class AntexProbeResult:
    """Result of probing a server for an ANTEX file."""
    label: str
    url: str
    found: bool
    filename: Optional[str] = None
    status_code: Optional[int] = None


def probe_http_file(label: str, result: AntexFileResult) -> AntexProbeResult:
    """
    Check if an ANTEX file exists at the given HTTP location.
    Uses HEAD request to verify file availability without downloading.
    """
    if result is None or not result.full_url:
        logger.warning(f"[{label}] No URL to probe")
        return AntexProbeResult(label=label, url="", found=False)
    
    url = result.full_url
    logger.info(f"Probing {label}: {url}")
    
    try:
        response = requests.head(url, timeout=30, allow_redirects=True)
        found = response.status_code == 200
        if found:
            logger.info(f"[{label}] Found: {result.filename} (HTTP {response.status_code})")
        else:
            logger.warning(f"[{label}] Not found: HTTP {response.status_code}")
        return AntexProbeResult(
            label=label, 
            url=url, 
            found=found, 
            filename=result.filename,
            status_code=response.status_code
        )
    except requests.RequestException as e:
        logger.error(f"[{label}] Request failed: {e}")
        return AntexProbeResult(label=label, url=url, found=False)


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

@pytest.fixture(scope="module")
def igs_source() -> IGSAntexHTTPSource:
    return IGSAntexHTTPSource()


@pytest.fixture(scope="module")
def ngs_source() -> NGSNOAAAntexHTTPSource:
    return NGSNOAAAntexHTTPSource()

IGS_CURRENT_LABEL = "igs_current"
IGS_ARCHIVED_LABEL = "igs_archived"
IGS_ITRF_14_LABEL = "igs14"
NGS_CURRENT_LABEL = "ngs_current"
NGS_PAST_LABEL = "ngs_past"
NGS_ITRF_14_LABEL = "ngs14_itrf"

@pytest.fixture(scope="module")
def igs_results(igs_source: IGSAntexHTTPSource, current_date: datetime.datetime, one_year_ago: datetime.datetime, itrf_14_date: datetime.datetime) -> dict[str, AntexProbeResult]:
    """Probe IGS HTTP server for ANTEX files."""
    results = {}
    
    # Current ATX
    igs_current_result:AntexFileResult = igs_source.query(current_date, strict=False)
    if igs_current_result:
        results[IGS_CURRENT_LABEL] = probe_http_file(IGS_CURRENT_LABEL, igs_current_result)
    
    # Archived IGS20 with week number (strict mode)
    igs_archived_strict:AntexFileResult = igs_source.query(one_year_ago, strict=True)
    if igs_archived_strict:
        results[IGS_ARCHIVED_LABEL] = probe_http_file(IGS_ARCHIVED_LABEL, igs_archived_strict)
    
    # itrf (2020 date)
    itrf_14_result:AntexFileResult = igs_source.query(itrf_14_date, strict=False)       
    if itrf_14_result:
        results[IGS_ITRF_14_LABEL] = probe_http_file(IGS_ITRF_14_LABEL, itrf_14_result)
    
    return results


@pytest.fixture(scope="module")
def ngs_results(ngs_source: NGSNOAAAntexHTTPSource,current_date: datetime.datetime, one_year_ago: datetime.datetime,itrf_14_date: datetime.datetime) -> dict[str, AntexProbeResult]:
    """Probe NGS/NOAA HTTP server for ANTEX files."""
    results = {}
    
    # NGS20 (2026 date)
    ngs20_result:AntexFileResult = ngs_source.query(current_date)
    
    if ngs20_result:
        results[NGS_CURRENT_LABEL] = probe_http_file(NGS_CURRENT_LABEL, ngs20_result)
    
    # NGS14 (2020 date)
    ngs14_result:AntexFileResult = ngs_source.query(one_year_ago)
    
    if ngs14_result:
        results[NGS_PAST_LABEL] = probe_http_file(NGS_PAST_LABEL, ngs14_result)

    # ITRF (2020 date)
    itrf_14_result:AntexFileResult = ngs_source.query(itrf_14_date)
   
    if itrf_14_result:
        results[NGS_ITRF_14_LABEL] = probe_http_file(NGS_ITRF_14_LABEL, itrf_14_result)
    
    return results


# ---------------------------------------------------------------------------
# Tests: IGS ANTEX HTTP Source
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestIGSAntexHTTPSource:
    """Test IGS ANTEX file availability via HTTP."""

    def test_igs_current_found(self, igs_results: dict[str, AntexProbeResult]) -> None:
        """IGS should provide current igs.atx file."""
        result = igs_results.get(IGS_CURRENT_LABEL)
        assert result is not None, "Query returned None"
        assert result.found, f"igs.atx not found at {result.url} (HTTP {result.status_code})"
        logger.info(f"[IGS] Current igs.atx found: {result.filename}")

    def test_igs_archived_found(self, igs_results: dict[str, AntexProbeResult]) -> None:
        """IGS should provide archived week-specific igs files."""
        result = igs_results.get(IGS_ARCHIVED_LABEL)
        assert result.found, f"Archived igs not found at {result.url}"
        assert "_" in result.filename, f"Expected week-specific file, got {result.filename}"
        logger.info(f"[IGS] Archived igs found: {result.filename}")

    def test_igs14_found(self, igs_results: dict[str, AntexProbeResult]) -> None:
        """IGS should provide igs14.atx for legacy processing."""
        result = igs_results.get(IGS_ITRF_14_LABEL)
        assert result is not None, "Query returned None"
        assert result.found, f"igs14.atx not found at {result.url}"
        logger.info(f"[IGS] igs14.atx found: {result.filename}")

    def test_frame_auto_detection(self, igs_source: IGSAntexHTTPSource) -> None:
        """Query should return correct frame based on date."""
        # 2026 -> igs20
        # 2020 -> igs14
        # 2011 -> igs05

        result_2026:IGSAntexReferenceFrameType = determine_frame(datetime.datetime(2026, 1, 1))
        assert result_2026 is not None
        assert result_2026 == IGSAntexReferenceFrameType.IGS20
        
        # 2020 -> igs14
        result_2020:IGSAntexReferenceFrameType = determine_frame(datetime.datetime(2020, 1, 1))
        assert result_2020 is not None
        assert result_2020 == IGSAntexReferenceFrameType.IGS14

        result_2014:IGSAntexReferenceFrameType = determine_frame(datetime.datetime(2012, 1, 1))
        assert result_2014 is not None
        assert result_2014 == IGSAntexReferenceFrameType.IGS08

        result_2011:IGSAntexReferenceFrameType = determine_frame(datetime.datetime(2011, 1, 1))
        assert result_2011 is not None
        assert result_2011 == IGSAntexReferenceFrameType.IGS05

    def test_query_returns_full_url(self, igs_source: IGSAntexHTTPSource,current_date: datetime.datetime) -> None:
        """Query result should include full download URL."""
        result = igs_source.query(current_date, strict=False)
        assert result is not None
        assert result.full_url.startswith("https://")
        assert "igs20" in result.full_url
        assert result.full_url.endswith(".atx")


# ---------------------------------------------------------------------------
# Tests: NGS/NOAA ANTEX HTTP Source
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestNGSAntexHTTPSource:
    """Test NGS/NOAA ANTEX file availability via HTTP."""

    def test_ngs20_found(self, ngs_results: dict[str, AntexProbeResult]) -> None:
        """NGS should provide ngs20.atx file."""
        result = ngs_results.get(NGS_CURRENT_LABEL)
        assert result is not None, "Query returned None"
        assert result.found, f"ngs.atx not found at {result.url} (HTTP {result.status_code})"
        logger.info(f"[NGS] ngs.atx found: {result.filename}")

    def test_ngs14_found(self, ngs_results: dict[str, AntexProbeResult]) -> None:
        """NGS should provide ngs14.atx for legacy processing."""
        result = ngs_results.get(NGS_ITRF_14_LABEL)
        assert result is not None, "Query returned None"
        assert result.found, f"ngs14.atx not found at {result.url}"
        logger.info(f"[NGS] ngs14.atx found: {result.filename}")

    def test_frame_auto_detection(self, ngs_source: NGSNOAAAntexHTTPSource,current_date: datetime.datetime,itrf_14_date: datetime.datetime) -> None:
        """Query should return correct frame based on date."""
        # 2026 -> ngs20
        result_2026 = ngs_source.query(current_date)
        assert result_2026 is not None
        assert result_2026.filename == "ngs20.atx"
        assert result_2026.frame_type == IGSAntexReferenceFrameType.IGS20
        
        # 2020 -> ngs14
        result_2020 = ngs_source.query(itrf_14_date)
        assert result_2020 is not None
        assert result_2020.filename == "ngs14.atx"
        assert result_2020.frame_type == IGSAntexReferenceFrameType.IGS14

    def test_query_returns_full_url(self, ngs_source: NGSNOAAAntexHTTPSource,current_date: datetime.datetime) -> None:
        """Query result should include full download URL."""
        result = ngs_source.query(current_date)
        assert result is not None
        assert result.full_url.startswith("https://")
        assert "ngs20.atx" in result.full_url


# ---------------------------------------------------------------------------
# Tests: Comparison between sources
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestAntexSourceComparison:
    """Compare IGS and NGS ANTEX sources."""

    def test_both_sources_return_same_frame_for_date(
        self, igs_source: IGSAntexHTTPSource, ngs_source: NGSNOAAAntexHTTPSource
    ) -> None:
        """Both sources should return the same reference frame for a given date."""
        date = datetime.datetime(2025, 6, 15)
        
        igs_result = igs_source.query(date, strict=False)
        ngs_result = ngs_source.query(date)
        
        assert igs_result is not None
        assert ngs_result is not None
        assert igs_result.frame_type == ngs_result.frame_type

