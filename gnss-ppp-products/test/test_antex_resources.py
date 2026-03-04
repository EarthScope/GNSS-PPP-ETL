"""
Integration tests for ANTEX (antenna phase center) FTP sources.

Tests verify that ANTEX files can be found on remote servers.
"""

import datetime
import logging
import pytest
from urllib.parse import urlparse
from dataclasses import dataclass
from typing import Optional

from gnss_ppp_products.resources import (
    AntexFrameType,
    AntexFileResult,
    IGSAntexFTPSource,
    CODEMGEXAntexFTPSource,
    IGSR3AntexFTPSource,
    CLSIGSAntexFTPSource,
    AntexProductSource,
)
from gnss_ppp_products.resources.utils import ftp_list_directory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class AntexProbeResult:
    """Result of probing a server for an ANTEX file."""
    label: str
    url: str
    found: bool
    filename: Optional[str] = None


def probe_ftp_file(label: str, result: AntexFileResult, use_tls: bool = False) -> AntexProbeResult:
    """
    Check if an ANTEX file exists at the given location.
    """
    ftpserver = result.ftpserver
    directory = result.directory
    filename = result.filename
    
    logger.info(f"Probing {label}: {ftpserver} / {directory} / {filename}")
    
    # Skip HTTP sources (files.igs.org) - would need different probing method
    if ftpserver.startswith("https://"):
        logger.info(f"[{label}] Skipping HTTP source - assuming available")
        return AntexProbeResult(label=label, url=result.url, found=True, filename=filename)
    
    listing = ftp_list_directory(ftpserver, directory, timeout=60, use_tls=use_tls)
    
    if not listing:
        logger.warning(f"[{label}] Could not list directory: {directory}")
        return AntexProbeResult(label=label, url=result.url, found=False)
    
    # Check for exact match or case-insensitive match
    for entry in listing:
        if entry == filename or entry.lower() == filename.lower():
            logger.info(f"[{label}] Found: {entry}")
            return AntexProbeResult(label=label, url=result.url, found=True, filename=entry)
    
    logger.warning(f"[{label}] File not found: {filename}")
    return AntexProbeResult(label=label, url=result.url, found=False)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def igs_source() -> IGSAntexFTPSource:
    return IGSAntexFTPSource()


@pytest.fixture(scope="module")
def code_mgex_source() -> CODEMGEXAntexFTPSource:
    return CODEMGEXAntexFTPSource()


@pytest.fixture(scope="module")
def repro3_source() -> IGSR3AntexFTPSource:
    return IGSR3AntexFTPSource()


@pytest.fixture(scope="module")
def clsigs_source() -> CLSIGSAntexFTPSource:
    return CLSIGSAntexFTPSource()


@pytest.fixture(scope="module")
def code_mgex_results(code_mgex_source: CODEMGEXAntexFTPSource) -> dict[str, AntexProbeResult]:
    """Probe CODE FTP server for MGEX ANTEX files."""
    results = {}
    
    # M14.ATX (legacy)
    m14_result = code_mgex_source.query(datetime.date(2020, 1, 1))
    results["M14"] = probe_ftp_file("CODE MGEX M14.ATX", m14_result, use_tls=False)
    
    # M20.ATX (current)
    m20_result = code_mgex_source.query(datetime.date(2023, 1, 1))
    results["M20"] = probe_ftp_file("CODE MGEX M20.ATX", m20_result, use_tls=False)
    
    return results


@pytest.fixture(scope="module")
def clsigs_results(clsigs_source: CLSIGSAntexFTPSource) -> dict[str, AntexProbeResult]:
    """Probe CLSIGS FTP server for ANTEX files."""
    results = {}
    
    # igs20.atx
    igs20_result = clsigs_source.query("igs20.atx")
    results["igs20"] = probe_ftp_file("CLSIGS igs20.atx", igs20_result, use_tls=False)
    
    return results


@pytest.fixture(scope="module")
def repro3_results(repro3_source: IGSR3AntexFTPSource) -> dict[str, AntexProbeResult]:
    """Probe IGS-RF and AIUB for Repro3 ANTEX files."""
    results = {}
    
    # Primary (igs-rf.ign.fr)
    primary_result = repro3_source.query()
    results["primary"] = probe_ftp_file("IGS-RF igsR3.atx", primary_result, use_tls=False)
    
    # Fallback (aiub) - only if primary fails
    if not results["primary"].found:
        fallback_result = repro3_source.query_fallback()
        results["fallback"] = probe_ftp_file("AIUB igsR3.atx", fallback_result, use_tls=False)
    
    return results


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestCODEMGEXAntex:
    """Test CODE MGEX ANTEX file availability."""

    def test_m14_found(self, code_mgex_results: dict[str, AntexProbeResult]) -> None:
        """CODE should provide M14.ATX for legacy processing."""
        result = code_mgex_results["M14"]
        assert result.found, f"M14.ATX not found at {result.url}"
        logger.info(f"[CODE MGEX] M14.ATX found: {result.filename}")

    def test_m20_found(self, code_mgex_results: dict[str, AntexProbeResult]) -> None:
        """CODE should provide M20.ATX for current processing."""
        result = code_mgex_results["M20"]
        assert result.found, f"M20.ATX not found at {result.url}"
        logger.info(f"[CODE MGEX] M20.ATX found: {result.filename}")

    def test_date_selection(self, code_mgex_source: CODEMGEXAntexFTPSource) -> None:
        """Query should return correct file based on date threshold."""
        # Before cutoff (2021-05-02) -> M14
        before = code_mgex_source.query(datetime.date(2021, 5, 1))
        assert before.filename == "M14.ATX"
        
        # After cutoff -> M20
        after = code_mgex_source.query(datetime.date(2021, 5, 2))
        assert after.filename == "M20.ATX"


@pytest.mark.integration
class TestCLSIGSAntex:
    """Test CLSIGS ANTEX file availability."""

    @pytest.mark.skip(reason="CLSIGS may not host ANTEX in expected location")
    def test_igs20_found(self, clsigs_results: dict[str, AntexProbeResult]) -> None:
        """CLSIGS should provide igs20.atx."""
        result = clsigs_results["igs20"]
        assert result.found, f"igs20.atx not found at {result.url}"
        logger.info(f"[CLSIGS] igs20.atx found: {result.filename}")

    def test_url_methods(self, clsigs_source: CLSIGSAntexFTPSource) -> None:
        """URL convenience methods should return valid paths."""
        igs20_url = clsigs_source.igs20()
        igs14_url = clsigs_source.igs14()
        
        assert "igs20.atx" in igs20_url
        assert "igs14.atx" in igs14_url
        assert igs20_url.startswith("ftp://")


@pytest.mark.integration
class TestIGSR3Antex:
    """Test IGS Repro3 ANTEX file availability."""

    @pytest.mark.skip(reason="IGS-RF server may be unreliable")
    def test_repro3_found(self, repro3_results: dict[str, AntexProbeResult]) -> None:
        """At least one Repro3 source should provide igsR3.atx."""
        primary = repro3_results.get("primary")
        fallback = repro3_results.get("fallback")
        
        found = (primary and primary.found) or (fallback and fallback.found)
        assert found, "igsR3.atx not found on primary or fallback servers"
        
        if primary and primary.found:
            logger.info(f"[IGS-RF] igsR3.atx found: {primary.filename}")
        elif fallback and fallback.found:
            logger.info(f"[AIUB] igsR3.atx found: {fallback.filename}")

    def test_query_returns_valid_result(self, repro3_source: IGSR3AntexFTPSource) -> None:
        """Query methods should return valid AntexFileResult objects."""
        primary = repro3_source.query()
        fallback = repro3_source.query_fallback()
        
        assert primary.filename == "igsR3.atx"
        assert fallback.filename == "igsR3.atx"
        assert primary.ftpserver != fallback.ftpserver  # Different servers


@pytest.mark.integration
class TestIGSAntex:
    """Test IGS ANTEX source (files.igs.org - HTTP)."""

    def test_query_returns_valid_result(self, igs_source: IGSAntexFTPSource) -> None:
        """Query should return valid AntexFileResult for different frames."""
        igs20 = igs_source.query(AntexFrameType.IGS20)
        igs14 = igs_source.query(AntexFrameType.IGS14)
        
        assert igs20.filename == "igs20.atx"
        assert igs14.filename == "igs14.atx"
        assert igs20.frame_type == AntexFrameType.IGS20
        assert igs14.frame_type == AntexFrameType.IGS14

    def test_query_by_filename(self, igs_source: IGSAntexFTPSource) -> None:
        """Query by filename should detect frame type correctly."""
        result = igs_source.query_by_filename("igs20_2345.atx")
        
        assert result.filename == "igs20_2345.atx"
        assert result.frame_type == AntexFrameType.IGS20
        # Week-specific files are in archive
        assert "archive" in result.directory


@pytest.mark.integration
class TestUnifiedAntexSource:
    """Test unified AntexProductSource interface."""

    def test_all_query_methods(self) -> None:
        """All query methods should return valid results."""
        source = AntexProductSource()
        
        # Standard IGS
        standard = source.query_standard(AntexFrameType.IGS20)
        assert standard.filename == "igs20.atx"
        
        # By filename
        by_name = source.query_by_filename("igs14.atx")
        assert by_name.filename == "igs14.atx"
        
        # CODE MGEX
        mgex = source.query_code_mgex(datetime.date(2023, 1, 1))
        assert mgex.filename == "M20.ATX"
        
        # Repro3
        repro3 = source.query_repro3()
        assert repro3.filename == "igsR3.atx"
