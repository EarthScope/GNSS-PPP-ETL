"""
Integration test suite: highest-quality GNSS products from FTP sources.

Metadata
--------
Date under test : 2025-01-01  (DOY 001, GPS week 2347)
FTP sources     : WuhanFTPProductSource, CLSIGSFTPProductSource
Quality fallback: FINAL → RAPID → REAL_TIME_STREAMING
Products probed : SP3  CLK  OBX  ERP  BIAS

Usage
-----
Run all integration tests::

    uv run pytest test/test_remote_resources.py -v

Skip in offline environments::

    uv run pytest -m "not integration"
"""
from __future__ import annotations

from collections import defaultdict
import datetime
import logging
from dataclasses import dataclass, field
from typing import Optional, Type

import pytest

from gnss_ppp_products.resources import WuhanFTPProductSource, CLSIGSFTPProductSource,KASDIFTPProductSource,CDDISFTPProductSource
from gnss_ppp_products.resources.base import FTPFileResult, FTPProductSource, ProductQuality

log = logging.getLogger(__name__)

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Test parameters
# ---------------------------------------------------------------------------

DATE = datetime.date(2025, 1, 1)
DOY: int = DATE.timetuple().tm_yday                            # 1
GPS_WEEK: int = (DATE - datetime.date(1980, 1, 6)).days // 7  # 2347

PRODUCTS: list[str] = ["sp3", "clk", "obx", "erp", "bias"]

QUALITY_ORDER: list[ProductQuality] = [
    ProductQuality.FINAL,
    ProductQuality.RAPID,
    ProductQuality.REAL_TIME_STREAMING,
]

# FTP sources to test
FTP_SOURCES: list[tuple[str, Type[FTPProductSource]]] = [
    ("Wuhan", WuhanFTPProductSource),
    ("CLSIGS", CLSIGSFTPProductSource),
    ("KASDI", KASDIFTPProductSource),
    ("CDDIS", CDDISFTPProductSource),
]


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass
class ProbeResult:
    """Outcome of querying a single GNSS product type across all quality levels."""

    product: str
    file_result: Optional[FTPFileResult] = None
    quality: Optional[ProductQuality] = None
    errors: dict[str, str] = field(default_factory=dict)  # quality.value → exc message

    @property
    def found(self) -> bool:
        return self.file_result is not None

    @property
    def quality_label(self) -> str:
        return self.quality.value if self.quality else "—"

    @property
    def filename(self) -> str:
        return self.file_result.filename if self.file_result else "not found"

    @property
    def url(self) -> str:
        return self.file_result.url if self.file_result else "—"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def product_results_by_source() -> dict[str, dict[str, dict[str, ProbeResult]]]:
    """
    Query all FTP servers for every product type, trying FINAL → RAPID → RTS.

    Results are cached at module scope so each FTP server is contacted only
    once per test session regardless of how many test functions consume this
    fixture.

    Returns:
        dict mapping source_name → product → quality → ProbeResult
    """
    all_results: dict[str, dict[str, dict[str, ProbeResult]]] = {}

    for source_name, source_cls in FTP_SOURCES:
        source = source_cls()
        results: dict[str, dict[str, ProbeResult]] = defaultdict(dict)

        log.info("Probing %s FTP — %s (DOY %03d, GPS week %d)", source_name, DATE, DOY, GPS_WEEK)

        for product in PRODUCTS:
            found_any = False

            for quality in QUALITY_ORDER:
                probe = ProbeResult(product=product)
                try:
                    file_result = source.query(
                        product=product, date=DATE, quality=quality
                    )
                except Exception as exc:
                    probe.errors[quality.value] = str(exc)
                    log.warning(
                        "  [%s] %s — ERROR: %s", product.upper(), quality.value, exc
                    )
                    file_result = None

                if file_result is not None:
                    probe.file_result = file_result
                    probe.quality = quality
                    found_any = True
                    log.info(
                        "  [%s] Found at %-3s — %s",
                        product.upper(),
                        quality.value,
                        file_result.filename,
                    )
                    results[product][quality] = probe

            if not found_any:
                tried = " → ".join(q.value for q in QUALITY_ORDER)
                log.warning("  [%s] Not found at any quality (%s)", product.upper(), tried)

        _print_summary(source_name, source.product_directory_source.ftpserver, results)
        all_results[source_name] = results

    return all_results


# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------

_COL_PROD = 8
_COL_QUAL = 7
_COL_FILE = 52


def _print_summary(source_name: str, ftpserver: str, results: dict[str, dict[str, ProbeResult]]) -> None:
    """Print a formatted ASCII table of query results to stdout."""
    separator = "=" * 80
    print(
        f"\n{separator}\n"
        f"  {source_name} FTP — Highest Quality Products\n"
        f"  Date: {DATE}  |  DOY: {DOY:03d}  |  GPS Week: {GPS_WEEK}\n"
        f"  Server: {ftpserver}\n"
        f"{separator}"
    )
    print(
        f"  {'Product':<{_COL_PROD}}"
        f"  {'Quality':<{_COL_QUAL}}"
        f"  {'Filename':<{_COL_FILE}}"
        f"  FTP URL"
    )
    print(
        f"  {'-'*_COL_PROD}"
        f"  {'-'*_COL_QUAL}"
        f"  {'-'*_COL_FILE}"
        f"  {'-'*60}"
    )
    for product, quality_dict in results.items():
        for quality, probe in quality_dict.items():
            print(
                f"  {probe.product.upper():<{_COL_PROD}}"
                f"  {probe.quality_label:<{_COL_QUAL}}"
                f"  {probe.filename:<{_COL_FILE}}"
                f"  {probe.url}"
            )
            for q_val, msg in probe.errors.items():
                print(f"    {'':>{_COL_PROD}}  {q_val}: {msg}")

    print(f"{separator}\n")


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("source_name,source_cls", FTP_SOURCES, ids=[s[0] for s in FTP_SOURCES])
class TestFTPHighestQuality:
    """
    Integration tests against FTP servers.

    Each test validates a single product type in isolation so failures are
    immediately identifiable by test name. Tests are parametrized to run
    against all configured FTP sources.

    Requires live network access.  Skip offline::

        pytest -m "not integration"
    """

    @pytest.fixture(autouse=True)
    def _setup(self, source_name: str, source_cls: Type[FTPProductSource], product_results_by_source: dict):
        """Setup source and results for each test."""
        self.source_name = source_name
        self.source = source_cls()
        self.product_results = product_results_by_source.get(source_name, {})

    def test_sp3_found_at_high_quality(self) -> None:
        """SP3 (precise orbit) must be present at FINAL or RAPID quality."""
        probe_sp3 = self.product_results.get("sp3", {})
        days_past = (datetime.date.today() - DATE).days
        found_quality = False
        for quality, probe in probe_sp3.items():
            assert probe.found, (
                f"[{self.source_name}] SP3 not found for {DATE} (DOY {DOY:03d}, GPS week {GPS_WEEK}). "
                f"Errors: {probe.errors or 'none — FTP listing returned no match'}."
            )
            if probe.quality in (ProductQuality.FINAL, ProductQuality.RAPID):
                found_quality = True
                log.info(
                    "[%s] SP3 found at %s quality for date %s (DOY %03d, GPS week %d).",
                    self.source_name,
                    probe.quality_label,
                    DATE,
                    DOY,
                    GPS_WEEK,
                )
        assert found_quality, (
            f"[{self.source_name}] SP3 found only at lower quality levels; expected FINAL or RAPID "
            f"for a date {days_past} days in the past."
        )

    def test_clk_found_at_high_quality(self) -> None:
        """CLK (precise clock) must be present at FINAL or RAPID quality."""
        probe_clock_results = self.product_results.get("clk", {})
        days_past = (datetime.date.today() - DATE).days
        found_quality = False
        for quality, probe in probe_clock_results.items():
            assert probe.found, (
                f"[{self.source_name}] CLK not found for {DATE} (DOY {DOY:03d}, GPS week {GPS_WEEK}). {quality.value} "
                f"Errors: {probe.errors or 'none — FTP listing returned no match'}."
            )
            if probe.quality in (ProductQuality.FINAL, ProductQuality.RAPID):
                found_quality = True
                log.info(
                    "[%s] CLK found at %s quality for date %s (DOY %03d, GPS week %d).",
                    self.source_name,
                    probe.quality_label,
                    DATE,
                    DOY,
                    GPS_WEEK,
                )
        assert found_quality, (
            f"[{self.source_name}] CLK found only at lower quality levels; expected FINAL or RAPID "
            f"for a date {days_past} days in the past."
        )

    def test_obx_found_at_high_quality(self) -> None:
        """OBX (satellite attitude quaternions) must be present at FINAL or RAPID quality."""
        probe_obx_results = self.product_results.get("obx", {})
        days_past = (datetime.date.today() - DATE).days
        found_quality = False
        for quality, probe in probe_obx_results.items():
            assert probe.found, (
                f"[{self.source_name}] OBX not found for {DATE} (DOY {DOY:03d}). {quality.value} "
                f"Errors: {probe.errors or 'none — FTP listing returned no match'}. "
                "Verify the OBX directory path and regex in Group1FileRegex."
            )
            if probe.quality in (ProductQuality.FINAL, ProductQuality.RAPID):
                found_quality = True
                log.info(
                    "[%s] OBX found at %s quality for date %s (DOY %03d).",
                    self.source_name,
                    probe.quality_label,
                    DATE,
                    DOY,
                )
        assert found_quality, (
            f"[{self.source_name}] OBX found only at lower quality levels; expected FINAL or RAPID "
            f"for a date {days_past} days in the past."
        )

    def test_erp_found_at_high_quality(self) -> None:
        """ERP (earth rotation parameters) must be present at FINAL or RAPID quality."""
        probe_erp = self.product_results.get("erp", {})
        days_past = (datetime.date.today() - DATE).days
        found_quality = False

        for quality, probe in probe_erp.items():
            assert probe.found, (
                f"[{self.source_name}] ERP not found for {DATE} (DOY {DOY:03d}). {quality.value} "
                f"Errors: {probe.errors or 'none — FTP listing returned no match'}. "
                "Verify the ERP directory path and regex in Group1FileRegex."
            )
            if probe.quality in (ProductQuality.FINAL, ProductQuality.RAPID):
                found_quality = True
                log.info(
                    "[%s] ERP found at %s quality for date %s (DOY %03d).",
                    self.source_name,
                    probe.quality_label,
                    DATE,
                    DOY,
                )
        assert found_quality, (
            f"[{self.source_name}] ERP found only at lower quality levels; expected FINAL or RAPID "
            f"for a date {days_past} days in the past."
        )

    def test_bias_found(self) -> None:
        """BIAS (satellite phase biases) must be present at any quality."""
        probe_bias = self.product_results.get("bias", {})
        days_past = (datetime.date.today() - DATE).days
        found_quality = False

        for quality, probe in probe_bias.items():
            assert probe.found, (
                f"[{self.source_name}] BIAS not found for {DATE} (DOY {DOY:03d}). {quality.value} "
                f"Errors: {probe.errors or 'none — FTP listing returned no match'}. "
                "Verify the BIAS directory path and regex in Group1FileRegex."
            )
            if probe.quality in (ProductQuality.FINAL, ProductQuality.RAPID):
                found_quality = True
                log.info(
                    "[%s] BIAS found at %s quality for date %s (DOY %03d).",
                    self.source_name,
                    probe.quality_label,
                    DATE,
                    DOY,
                )
        assert found_quality, (
            f"[{self.source_name}] BIAS found only at lower quality levels; expected FINAL or RAPID "
            f"for a date {days_past} days in the past."
        )

    def test_found_products_have_valid_filenames(self) -> None:
        """Every product that resolved must have a non-empty, extension-bearing filename."""
        for product, probe_qualities in self.product_results.items():
            for quality, probe in probe_qualities.items():
                if not probe.found:
                    continue
                assert probe.filename, (
                    f"[{self.source_name}] {product.upper()} result has an empty filename."
                )
                assert "." in probe.filename, (
                    f"[{self.source_name}] {product.upper()} filename '{probe.filename}' has no file extension."
                )

    def test_found_products_have_valid_ftp_urls(self) -> None:
        """Every product that resolved must produce a well-formed FTP URL."""
        for product, probe_qualities in self.product_results.items():
            for quality, probe in probe_qualities.items():
                if not probe.found:
                    continue
                assert probe.url.startswith("ftp://"), (
                    f"[{self.source_name}] {product.upper()} URL '{probe.url}' does not start with 'ftp://'."
                )
                assert probe.filename in probe.url, (
                    f"[{self.source_name}] {product.upper()} URL '{probe.url}' does not contain its filename."
                )
