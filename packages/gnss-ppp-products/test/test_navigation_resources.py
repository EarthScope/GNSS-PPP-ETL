"""
Integration test suite: Navigation (broadcast ephemeris) products from FTP sources.

Metadata
--------
Dates under test:
    RINEX v3: 2025-01-01  (DOY 001, GPS week 2347) - modern merged broadcast
    RINEX v2: 2020-01-01  (DOY 001, GPS week 2086) - legacy per-constellation
Products probed : rinex_3_nav (BRDC), rinex_2_nav (GPS/GLONASS)
FTP sources     : WuhanNavFileFTPProductSource

Usage
-----
Run all integration tests::

    uv run pytest test/test_navigation_resources.py -v

Skip in offline environments::

    uv run pytest -m "not integration"
"""
from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass, field
from typing import Optional, Type

import pytest

from gnss_ppp_products.resources import (
    WuhanNavFileFTPProductSource, 
    CLSIGSNavFileFTPProductSource,
    CDDISNavFileFTPProductSource
)
from gnss_ppp_products.resources.remote.base import (
    FTPFileResult,
    FTPProductSource,
    ProductQuality,
    ConstellationCode,
)

log = logging.getLogger(__name__)

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Test parameters
# ---------------------------------------------------------------------------

# RINEX v3 merged broadcast - available on modern servers
DATE_RINEX_3 = datetime.date(2025, 1, 1)
DOY_RINEX_3: int = DATE_RINEX_3.timetuple().tm_yday  # 1
GPS_WEEK_RINEX_3: int = (DATE_RINEX_3 - datetime.date(1980, 1, 6)).days // 7  # 2347

# RINEX v2 legacy format - use older date when these were more common
DATE_RINEX_2 = datetime.date(2010, 1, 1)
DOY_RINEX_2: int = DATE_RINEX_2.timetuple().tm_yday  # 1
GPS_WEEK_RINEX_2: int = (DATE_RINEX_2 - datetime.date(1980, 1, 6)).days // 7  # 2086

# Navigation product types to test: (product_type, constellation, date)
NAV_PRODUCTS = [
    ("rinex_3_nav", None, DATE_RINEX_3),  # RINEX v3 merged broadcast
    ("rinex_2_nav", ConstellationCode.GPS, DATE_RINEX_2),  # GPS navigation
    ("rinex_2_nav", ConstellationCode.GLONASS, DATE_RINEX_2),  # GLONASS navigation
    ("rinex_3_nav",None,DATE_RINEX_3), # RINEX v3 merged broadcast (repeat to check multi-constellation handling)
]

# FTP sources to test (only Wuhan has nav files in known locations)
FTP_SOURCES: list[tuple[str, Type[FTPProductSource]]] = [
    ("Wuhan", WuhanNavFileFTPProductSource),
    ("CLSIGS", CLSIGSNavFileFTPProductSource),
    ("CDDIS", CDDISNavFileFTPProductSource),
]


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass
class NavProbeResult:
    """Outcome of querying a navigation product."""

    product: str
    date: datetime.date
    constellation: Optional[ConstellationCode] = None
    file_result: Optional[FTPFileResult] = None
    error: Optional[str] = None

    @property
    def found(self) -> bool:
        return self.file_result is not None

    @property
    def doy(self) -> int:
        return self.date.timetuple().tm_yday

    @property
    def filename(self) -> str:
        return self.file_result.filename if self.file_result else "not found"

    @property
    def url(self) -> str:
        return self.file_result.url if self.file_result else "—"

    @property
    def label(self) -> str:
        if self.constellation:
            return f"{self.product} ({self.constellation.name})"
        return self.product


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def nav_results_by_source() -> dict[str, dict[str, NavProbeResult]]:
    """
    Query all FTP servers for navigation products.

    Returns:
        dict mapping source_name → product_label → NavProbeResult
    """
    all_results: dict[str, dict[str, NavProbeResult]] = {}

    for source_name, source_cls in FTP_SOURCES:
        source = source_cls()
        results: dict[str, NavProbeResult] = {}

        log.info("Probing %s FTP for navigation products", source_name)

        for product, constellation, date in NAV_PRODUCTS:
            doy = date.timetuple().tm_yday
            probe = NavProbeResult(product=product, date=date, constellation=constellation)

            log.info(
                "  Querying %s for %s (DOY %03d)",
                probe.label,
                date,
                doy,
            )

            try:
                file_result = source.query(
                    product=product,
                    date=date,
                    constellation=constellation,
                )
            except Exception as exc:
                probe.error = str(exc)
                log.warning("  [%s] ERROR: %s", probe.label, exc)
                file_result = None

            if file_result is not None:
                probe.file_result = file_result
                log.info("  [%s] Found — %s", probe.label, file_result.filename)
            else:
                log.warning("  [%s] Not found", probe.label)

            results[probe.label] = probe

        _print_summary(source_name, source.product_directory_source.ftpserver, results)
        all_results[source_name] = results

    return all_results


# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------

_COL_PROD = 24
_COL_FILE = 40


def _print_summary(
    source_name: str, ftpserver: str, results: dict[str, NavProbeResult]
) -> None:
    """Print a formatted ASCII table of query results to stdout."""
    separator = "=" * 100
    print(
        f"\n{separator}\n"
        f"  {source_name} FTP — Navigation Products\n"
        f"  Server: {ftpserver}\n"
        f"{separator}"
    )
    print(
        f"  {'Product':<{_COL_PROD}}"
        f"  {'Date':<12}"
        f"  {'Filename':<{_COL_FILE}}"
        f"  FTP URL"
    )
    print(
        f"  {'-'*_COL_PROD}"
        f"  {'-'*12}"
        f"  {'-'*_COL_FILE}"
        f"  {'-'*50}"
    )
    for label, probe in results.items():
        status = "✓" if probe.found else "✗"
        print(
            f"  {status} {label:<{_COL_PROD - 2}}"
            f"  {probe.date}"
            f"  {probe.filename:<{_COL_FILE}}"
            f"  {probe.url}"
        )
        if probe.error:
            print(f"    ERROR: {probe.error}")

    print(f"{separator}\n")


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "source_name,source_cls", FTP_SOURCES, ids=[s[0] for s in FTP_SOURCES]
)
class TestNavigationProducts:
    """
    Integration tests for navigation/broadcast ephemeris products.

    Tests RINEX v2 and v3 navigation files from FTP servers.

    Requires live network access. Skip offline::

        pytest -m "not integration"
    """

    @pytest.fixture(autouse=True)
    def _setup(
        self,
        source_name: str,
        source_cls: Type[FTPProductSource],
        nav_results_by_source: dict,
    ):
        """Setup source and results for each test."""
        self.source_name = source_name
        self.source = source_cls()
        self.nav_results = nav_results_by_source.get(source_name, {})

    def test_rinex3_nav_found(self) -> None:
        """RINEX v3 merged broadcast navigation (BRDC) must be available."""
        probe = self.nav_results.get("rinex_3_nav")
        assert probe is not None, "rinex_3_nav probe missing from results"
        assert probe.found, (
            f"[{self.source_name}] RINEX v3 navigation not found for {probe.date} "
            f"(DOY {probe.doy:03d}). Error: {probe.error or 'No match in FTP listing'}"
        )
        log.info(
            "[%s] RINEX v3 nav found: %s",
            self.source_name,
            probe.filename,
        )

    def test_rinex2_gps_nav_found(self) -> None:
        """RINEX v2 GPS navigation file may be available (legacy format)."""
        label = "rinex_2_nav (GPS)"
        probe = self.nav_results.get(label)
        assert probe is not None, f"{label} probe missing from results"
       
            
        log.info(
            "[%s] RINEX v2 GPS nav found: %s",
            self.source_name,
            probe.filename,
        )

    def test_rinex2_glonass_nav_found(self) -> None:
        """RINEX v2 GLONASS navigation file may be available (legacy format)."""
        label = "rinex_2_nav (GLONASS)"
        probe = self.nav_results.get(label)
        assert probe is not None, f"{label} probe missing from results"

        log.info(
            "[%s] RINEX v2 GLONASS nav found: %s",
            self.source_name,
            probe.filename,
        )

    def test_nav_filenames_have_extensions(self) -> None:
        """Found navigation files must have valid filename extensions."""
        for label, probe in self.nav_results.items():
            if not probe.found:
                continue
            assert probe.filename, f"[{self.source_name}] {label} has empty filename"
            assert "." in probe.filename, (
                f"[{self.source_name}] {label} filename '{probe.filename}' "
                "has no extension"
            )

    def test_nav_urls_are_valid(self) -> None:
        """Found navigation files must have valid FTP URLs."""
        for label, probe in self.nav_results.items():
            if not probe.found:
                continue
            assert probe.url.startswith("ftp://"), (
                f"[{self.source_name}] {label} URL '{probe.url}' "
                "does not start with 'ftp://'"
            )
            assert probe.filename in probe.url, (
                f"[{self.source_name}] {label} URL '{probe.url}' "
                "does not contain filename"
            )

    def test_nav_filenames_contain_date_info(self) -> None:
        """Navigation filenames should contain DOY or date identifiers."""
        for label, probe in self.nav_results.items():
            if not probe.found:
                continue
            # RINEX v2: brdc{doy}0.{yy}n.gz -> contains doy (001)
            # RINEX v3: BRDC00IGS_R_{year}{doy}... -> contains year and doy
            doy_str = f"{probe.doy:03d}"
            year_str = str(probe.date.year)
            has_date_info = doy_str in probe.filename or year_str in probe.filename
            assert has_date_info, (
                f"[{self.source_name}] {label} filename '{probe.filename}' "
                f"does not contain date identifiers (expected DOY={doy_str} or year={year_str})"
            )
