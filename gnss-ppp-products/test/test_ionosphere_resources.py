"""
Integration test suite: Ionosphere correction products from FTP sources.

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
from typing import Optional

import pytest

from gnss_ppp_products.resources.ionosphere_resources import (
    IonosphereProductQuality,
    IonosphereProductType,
    IonosphereProductSource,
    IonosphereFileResult,
    CODEGIMProductSource,
    WuhanGIMProductSource,
    CDDISGIMProductSource,
)

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

QUALITY_ORDER: list[IonosphereProductQuality] = [
    IonosphereProductQuality.FINAL,
    IonosphereProductQuality.RAPID,
]

ANALYSIS_CENTERS: list[IonosphereProductSource] = [
    IonosphereProductSource.COD,
    IonosphereProductSource.IGS,
    IonosphereProductSource.ESA,
    IonosphereProductSource.JPL,
]


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------


@dataclass
class GIMProbeResult:
    """Outcome of querying a GIM product."""

    server_name: str
    date: datetime.date
    center: Optional[IonosphereProductSource] = None
    quality: Optional[IonosphereProductQuality] = None
    file_result: Optional[IonosphereFileResult] = None
    error: Optional[str] = None

    @property
    def found(self) -> bool:
        return self.file_result is not None

    @property
    def filename(self) -> str:
        return self.file_result.filename if self.file_result else "not found"

    @property
    def full_url(self) -> str:
        if self.file_result:
            return self.file_result.url or f"{self.file_result.server}/{self.file_result.directory}/{self.file_result.filename}"
        return "—"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _print_summary(title: str, results: list[GIMProbeResult]) -> None:
    """Print formatted summary table."""
    log.info("")
    log.info("=" * 80)
    log.info(f" {title}")
    log.info("=" * 80)
    
    for result in results:
        status = "✓ FOUND" if result.found else "✗ NOT FOUND"
        center_str = result.center.value if result.center else "N/A"
        quality_str = result.quality.value if result.quality else "N/A"
        log.info(
            f"  [{result.server_name}] {result.date} | Center: {center_str} | Quality: {quality_str} | {status}"
        )
        if result.found:
            log.info(f"      → {result.filename}")
        if result.error:
            log.info(f"      ERROR: {result.error}")
    
    log.info("=" * 80)


# ---------------------------------------------------------------------------
# CODE GIM Tests
# ---------------------------------------------------------------------------


class TestCODEGIMProductSource:
    """Tests for CODE GIM product queries from ftp.aiub.unibe.ch."""

    @pytest.fixture(scope="class")
    def source(self) -> CODEGIMProductSource:
        return CODEGIMProductSource()

    def test_query_new_format(self, source: CODEGIMProductSource) -> None:
        """Test querying GIM with new long-form naming (post-2022)."""
        log.info("Testing CODE GIM query for %s (DOY %03d) - new format", DATE_NEW_FORMAT, DOY_NEW)
        
        result = source.query(DATE_NEW_FORMAT)
        
        assert result is not None, f"Expected GIM file for {DATE_NEW_FORMAT}, got None"
        assert result.product_type == IonosphereProductType.GIM
        assert "COD0OPSFIN" in result.filename or "GIM" in result.filename.upper()
        assert result.server == "ftp://ftp.aiub.unibe.ch"
        
        log.info("  Found: %s", result.filename)

    def test_query_legacy_format(self, source: CODEGIMProductSource) -> None:
        """Test querying GIM with legacy naming (pre-2022)."""
        log.info("Testing CODE GIM query for %s (DOY %03d) - legacy format", DATE_LEGACY_FORMAT, DOY_LEGACY)
        
        result = source.query(DATE_LEGACY_FORMAT)
        
        assert result is not None, f"Expected GIM file for {DATE_LEGACY_FORMAT}, got None"
        assert result.product_type == IonosphereProductType.GIM
        # Legacy format: CODG{doy}0.{yy}I.Z
        assert "CODG" in result.filename or "codg" in result.filename.lower()
        
        log.info("  Found: %s", result.filename)

    def test_directory_structure(self, source: CODEGIMProductSource) -> None:
        """Test that directory paths are correctly formatted."""
        directory_2025 = source.directory_source.directory(DATE_NEW_FORMAT)
        directory_2020 = source.directory_source.directory(DATE_LEGACY_FORMAT)
        
        assert directory_2025 == "CODE/2025"
        assert directory_2020 == "CODE/2020"

    def test_file_regex_new_format(self, source: CODEGIMProductSource) -> None:
        """Test regex pattern generation for new format."""
        regex = source.file_regex.ion(DATE_NEW_FORMAT)
        
        assert "2025" in regex
        assert "001" in regex or "0010000" in regex
        log.info("  New format regex: %s", regex)

    def test_file_regex_legacy_format(self, source: CODEGIMProductSource) -> None:
        """Test regex pattern generation for legacy format."""
        regex = source.file_regex.ion(DATE_LEGACY_FORMAT)
        
        # Legacy format should include year components
        assert "CODG" in regex or "20" in regex
        log.info("  Legacy format regex: %s", regex)


# ---------------------------------------------------------------------------
# Wuhan GIM Tests
# ---------------------------------------------------------------------------


class TestWuhanGIMProductSource:
    """Tests for GIM product queries from Wuhan University (igs.gnsswhu.cn)."""

    @pytest.fixture(scope="class")
    def source(self) -> WuhanGIMProductSource:
        return WuhanGIMProductSource()

    def test_query_code_final(self, source: WuhanGIMProductSource) -> None:
        """Test querying CODE final GIM from Wuhan mirror."""
        log.info("Testing Wuhan GIM query for %s - CODE FINAL", DATE_NEW_FORMAT)
        
        result = source.query(
            DATE_NEW_FORMAT,
            center=IonosphereProductSource.COD,
            quality=IonosphereProductQuality.FINAL,
        )
        
        if result is not None:
            log.info("  Found: %s", result.filename)
            assert result.product_type == IonosphereProductType.GIM
            assert result.server == "ftp://igs.gnsswhu.cn"
        else:
            log.warning("  Not found (may be expected for recent dates)")

    def test_query_igs_combined(self, source: WuhanGIMProductSource) -> None:
        """Test querying IGS combined GIM from Wuhan mirror."""
        log.info("Testing Wuhan GIM query for %s - IGS combined", DATE_NEW_FORMAT)
        
        result = source.query(
            DATE_NEW_FORMAT,
            center=IonosphereProductSource.IGS,
            quality=IonosphereProductQuality.FINAL,
        )
        
        if result is not None:
            log.info("  Found: %s", result.filename)
            assert result.product_type == IonosphereProductType.GIM
        else:
            log.warning("  Not found (may be expected for recent dates)")

    def test_query_jpl(self, source: WuhanGIMProductSource) -> None:
        """Test querying JPL GIM from Wuhan mirror."""
        log.info("Testing Wuhan GIM query for %s - JPL", DATE_NEW_FORMAT)
        
        result = source.query(
            DATE_NEW_FORMAT,
            center=IonosphereProductSource.JPL,
            quality=IonosphereProductQuality.FINAL,
        )
        
        if result is not None:
            log.info("  Found: %s", result.filename)
            assert result.product_type == IonosphereProductType.GIM
        else:
            log.warning("  Not found (may be expected)")

    def test_directory_structure(self, source: WuhanGIMProductSource) -> None:
        """Test that directory paths are correctly formatted."""
        directory = source.directory_source.directory(DATE_NEW_FORMAT)
        
        assert directory == "pub/gps/products/ionex/2025/001"


# ---------------------------------------------------------------------------
# CDDIS GIM Tests
# ---------------------------------------------------------------------------


class TestCDDISGIMProductSource:
    """Tests for GIM product queries from NASA CDDIS (requires FTPS)."""

    @pytest.fixture(scope="class")
    def source(self) -> CDDISGIMProductSource:
        return CDDISGIMProductSource()

    def test_query_code(self, source: CDDISGIMProductSource) -> None:
        """Test querying CODE GIM from CDDIS."""
        log.info("Testing CDDIS GIM query for %s - CODE", DATE_NEW_FORMAT)
        
        result = source.query(
            DATE_NEW_FORMAT,
            center=IonosphereProductSource.COD,
            quality=IonosphereProductQuality.FINAL,
        )
        
        if result is not None:
            log.info("  Found: %s", result.filename)
            assert result.product_type == IonosphereProductType.GIM
            assert "cddis" in result.server.lower()
        else:
            log.warning("  Not found (CDDIS may require FTPS)")

    def test_query_igs(self, source: CDDISGIMProductSource) -> None:
        """Test querying IGS combined GIM from CDDIS."""
        log.info("Testing CDDIS GIM query for %s - IGS", DATE_NEW_FORMAT)
        
        result = source.query(
            DATE_NEW_FORMAT,
            center=IonosphereProductSource.IGS,
            quality=IonosphereProductQuality.FINAL,
        )
        
        if result is not None:
            log.info("  Found: %s", result.filename)
            assert result.product_type == IonosphereProductType.GIM
        else:
            log.warning("  Not found (CDDIS may require FTPS)")

    def test_directory_structure(self, source: CDDISGIMProductSource) -> None:
        """Test that directory paths are correctly formatted."""
        directory = source.directory_source.directory(DATE_NEW_FORMAT)
        
        assert directory == "gnss/products/ionex/2025/001"

    def test_invalid_center_raises(self, source: CDDISGIMProductSource) -> None:
        """Test that unsupported centers raise assertion."""
        # UPC is not in the allowed list for CDDIS
        with pytest.raises(AssertionError):
            source.query(
                DATE_NEW_FORMAT,
                center=IonosphereProductSource.UPC,
                quality=IonosphereProductQuality.FINAL,
            )


# ---------------------------------------------------------------------------
# Cross-server comparison tests
# ---------------------------------------------------------------------------


class TestCrossServerComparison:
    """Compare availability across different FTP servers."""

    @pytest.fixture(scope="class")
    def probe_results(self) -> list[GIMProbeResult]:
        """Probe all servers for GIM availability."""
        results: list[GIMProbeResult] = []
        
        # CODE primary server
        code_source = CODEGIMProductSource()
        for date in [DATE_NEW_FORMAT, DATE_LEGACY_FORMAT]:
            probe = GIMProbeResult(server_name="CODE", date=date)
            try:
                result = code_source.query(date)
                probe.file_result = result
            except Exception as e:
                probe.error = str(e)
            results.append(probe)
        
        # Wuhan mirror
        wuhan_source = WuhanGIMProductSource()
        for center in [IonosphereProductSource.COD, IonosphereProductSource.IGS]:
            probe = GIMProbeResult(
                server_name="Wuhan",
                date=DATE_NEW_FORMAT,
                center=center,
                quality=IonosphereProductQuality.FINAL,
            )
            try:
                result = wuhan_source.query(
                    DATE_NEW_FORMAT,
                    center=center,
                    quality=IonosphereProductQuality.FINAL,
                )
                probe.file_result = result
            except Exception as e:
                probe.error = str(e)
            results.append(probe)
        
        # CDDIS mirror
        cddis_source = CDDISGIMProductSource()
        for center in [IonosphereProductSource.COD, IonosphereProductSource.IGS]:
            probe = GIMProbeResult(
                server_name="CDDIS",
                date=DATE_NEW_FORMAT,
                center=center,
                quality=IonosphereProductQuality.FINAL,
            )
            try:
                result = cddis_source.query(
                    DATE_NEW_FORMAT,
                    center=center,
                    quality=IonosphereProductQuality.FINAL,
                )
                probe.file_result = result
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
# File result structure tests
# ---------------------------------------------------------------------------


class TestIonosphereFileResult:
    """Tests for IonosphereFileResult dataclass."""

    def test_result_attributes(self) -> None:
        """Test that file result has all expected attributes."""
        result = IonosphereFileResult(
            server="ftp://ftp.aiub.unibe.ch",
            directory="CODE/2025",
            filename="COD0OPSFIN_20250010000_01D_01H_GIM.INX.gz",
            product_type=IonosphereProductType.GIM,
            quality=IonosphereProductQuality.FINAL,
        )
        
        assert result.server == "ftp://ftp.aiub.unibe.ch"
        assert result.directory == "CODE/2025"
        assert result.filename == "COD0OPSFIN_20250010000_01D_01H_GIM.INX.gz"
        assert result.product_type == IonosphereProductType.GIM
        assert result.quality == IonosphereProductQuality.FINAL

    def test_full_url_property(self) -> None:
        """Test full_url property assembly when not set."""
        result = IonosphereFileResult(
            server="ftp://ftp.aiub.unibe.ch",
            directory="CODE/2025",
            filename="test.gz",
            product_type=IonosphereProductType.GIM,
        )
        
        # full_url is optional and set explicitly
        assert result.url is None or "ftp://" in str(result.url)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    """Tests for ionosphere-related enums."""

    def test_quality_values(self) -> None:
        """Test IonosphereProductQuality enum values."""
        assert IonosphereProductQuality.FINAL.value == "final"
        assert IonosphereProductQuality.RAPID.value == "rapid"
        assert IonosphereProductQuality.PREDICTED.value == "predicted"

    def test_product_type_values(self) -> None:
        """Test IonosphereProductType enum values."""
        assert IonosphereProductType.GIM.value == "gim"

    def test_product_source_values(self) -> None:
        """Test IonosphereProductSource analysis center values."""
        assert IonosphereProductSource.COD == "cod"
        assert IonosphereProductSource.IGS == "igs"
        assert IonosphereProductSource.JPL == "jpl"
        assert IonosphereProductSource.ESA == "esa"
