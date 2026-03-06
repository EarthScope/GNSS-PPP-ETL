"""
Integration test suite: LEO satellite products from FTP sources.

Metadata
--------
Date under test : 2024-01-15 (GRACE-FO), 2016-06-15 (GRACE)
Products probed : Level-1B instrument data, GraceRead software
Servers         : GFZ Potsdam (isdcftp.gfz-potsdam.de)

Usage
-----
Run all integration tests::

    uv run pytest test/test_leo_resources.py -v

Skip in offline environments::

    uv run pytest -m "not integration"
"""
from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from typing import Optional

import pytest

from gnss_ppp_products.resources.leo_resources import (
    GRACEMission,
    GRACEInstrument,
    GRACEFileResult,
    GFZGRACEFTPProductSource,
)

log = logging.getLogger(__name__)

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Test parameters
# ---------------------------------------------------------------------------

# GRACE-FO test date (mission started 2018)
DATE_GRACE_FO = datetime.date(2024, 1, 15)

# Original GRACE test date (mission ended 2017)
DATE_GRACE = datetime.date(2016, 6, 15)

# Instruments to test
INSTRUMENTS: list[str] = ["GNV1B", "ACC1B", "SCA1B"]


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------


@dataclass
class GRACEProbeResult:
    """Outcome of querying a GRACE product."""

    mission: GRACEMission
    date: datetime.date
    instrument: str
    file_result: Optional[GRACEFileResult] = None
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


def _print_summary(title: str, results: list[GRACEProbeResult]) -> None:
    """Print formatted summary table."""
    log.info("")
    log.info("=" * 80)
    log.info(f" {title}")
    log.info("=" * 80)
    
    for result in results:
        status = "✓ FOUND" if result.found else "✗ NOT FOUND"
        log.info(
            f"  [{result.mission.value}] {result.date} | Instrument: {result.instrument} | {status}"
        )
        if result.found:
            log.info(f"      → {result.filename}")
        if result.error:
            log.info(f"      ERROR: {result.error}")
    
    log.info("=" * 80)


# ---------------------------------------------------------------------------
# GFZ GRACE/GRACE-FO Tests
# ---------------------------------------------------------------------------


class TestGFZGRACEFTPProductSource:
    """Tests for GRACE/GRACE-FO product queries from GFZ Potsdam."""

    @pytest.fixture(scope="class")
    def source(self) -> GFZGRACEFTPProductSource:
        return GFZGRACEFTPProductSource()

    def test_query_grace_fo_gnv1b(self, source: GFZGRACEFTPProductSource) -> None:
        """Test querying GRACE-FO GNV1B (GPS Navigation) data."""
        log.info("Testing GRACE-FO GNV1B query for %s", DATE_GRACE_FO)
        
        result = source.query(
            date=DATE_GRACE_FO,
            mission=GRACEMission.GRACE_FO,
            product="GNV1B",
        )
        
        # Note: This may return None if the GFZ FTP is unavailable
        if result is not None:
            assert result.mission == GRACEMission.GRACE_FO
            assert result.instrument == "GNV1B"
            log.info("  Found: %s", result.filename)
            log.info("  URL: %s", result.url)
        else:
            log.warning("  Product not found (FTP may be unavailable)")

    def test_query_grace_gnv1b(self, source: GFZGRACEFTPProductSource) -> None:
        """Test querying original GRACE GNV1B data."""
        log.info("Testing GRACE GNV1B query for %s", DATE_GRACE)
        
        result = source.query(
            date=DATE_GRACE,
            mission=GRACEMission.GRACE,
            product="GNV1B",
        )
        
        if result is not None:
            assert result.mission == GRACEMission.GRACE
            assert result.instrument == "GNV1B"
            log.info("  Found: %s", result.filename)
        else:
            log.warning("  Product not found")

    def test_mission_date_validation_grace_fo(self, source: GFZGRACEFTPProductSource) -> None:
        """Test that GRACE-FO rejects dates before 2018."""
        result = source.query(
            date=datetime.date(2015, 1, 1),
            mission=GRACEMission.GRACE_FO,
            product="GNV1B",
        )
        assert result is None

    def test_mission_date_validation_grace(self, source: GFZGRACEFTPProductSource) -> None:
        """Test that GRACE warns about dates after 2017."""
        result = source.query(
            date=datetime.date(2020, 1, 1),
            mission=GRACEMission.GRACE,
            product="GNV1B",
        )
        assert result is None

    def test_directory_structure_grace_fo(self, source: GFZGRACEFTPProductSource) -> None:
        """Test GRACE-FO directory path construction."""
        directory = source.directory_source.level1b_directory(
            DATE_GRACE_FO,
            GRACEMission.GRACE_FO,
            "GNV1B"
        )
        assert "grace-fo" in directory
        assert "Level-1B" in directory
        assert "2024" in directory
        assert "GNV1B" in directory

    def test_directory_structure_grace(self, source: GFZGRACEFTPProductSource) -> None:
        """Test original GRACE directory path construction."""
        directory = source.directory_source.level1b_directory(
            DATE_GRACE,
            GRACEMission.GRACE,
            "GNV1B"
        )
        assert "grace/" in directory or directory.startswith("grace/")
        assert "Level-1B" in directory
        assert "2016" in directory

    def test_file_regex_pattern(self, source: GFZGRACEFTPProductSource) -> None:
        """Test Level-1B file regex generation."""
        regex = source.file_regex.level1b(DATE_GRACE_FO, "GNV1B")
        
        assert "GNV1B" in regex
        assert "2024" in regex
        assert "01" in regex  # month
        assert "15" in regex  # day


# ---------------------------------------------------------------------------
# Summary test
# ---------------------------------------------------------------------------


class TestGRACESummary:
    """Summary test that probes GRACE products."""

    def test_all_instruments_grace_fo(self) -> None:
        """Probe all instruments for GRACE-FO and print summary."""
        source = GFZGRACEFTPProductSource()
        results: list[GRACEProbeResult] = []
        
        for instrument in INSTRUMENTS:
            try:
                file_result = source.query(
                    date=DATE_GRACE_FO,
                    mission=GRACEMission.GRACE_FO,
                    product=instrument,
                )
                results.append(GRACEProbeResult(
                    mission=GRACEMission.GRACE_FO,
                    date=DATE_GRACE_FO,
                    instrument=instrument,
                    file_result=file_result,
                ))
            except Exception as e:
                results.append(GRACEProbeResult(
                    mission=GRACEMission.GRACE_FO,
                    date=DATE_GRACE_FO,
                    instrument=instrument,
                    error=str(e),
                ))
        
        _print_summary("GRACE-FO Level-1B Products Summary", results)
