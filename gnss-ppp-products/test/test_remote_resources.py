"""
Integration test suite: highest-quality GNSS products from Wuhan IGS FTP.

Metadata
--------
Date under test : 2025-01-01  (DOY 001, GPS week 2347)
FTP source      : ftp://igs.gnsswhu.cn  (WuhanFTPProductSource)
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

import datetime
import logging
from dataclasses import dataclass, field
from typing import Optional

import pytest

from gnss_ppp_products.resources import WuhanFTPProductSource
from gnss_ppp_products.resources.base import FTPFileResult, ProductQuality

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
def wuhan_source() -> WuhanFTPProductSource:
    """Single WuhanFTPProductSource shared across all tests in this module."""
    return WuhanFTPProductSource()


@pytest.fixture(scope="module")
def product_results(wuhan_source: WuhanFTPProductSource) -> dict[str, ProbeResult]:
    """
    Query the Wuhan FTP server for every product type, trying FINAL → RAPID → RTS.

    Results are cached at module scope so the FTP server is contacted only
    once per test session regardless of how many test functions consume this
    fixture.
    """
    results: dict[str, ProbeResult] = {}

    log.info("Probing Wuhan IGS FTP — %s (DOY %03d, GPS week %d)", DATE, DOY, GPS_WEEK)

    for product in PRODUCTS:
        probe = ProbeResult(product=product)

        for quality in QUALITY_ORDER:
            try:
                file_result = wuhan_source.query(
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
                log.info(
                    "  [%s] Found at %-3s — %s",
                    product.upper(),
                    quality.value,
                    file_result.filename,
                )
                break

        if not probe.found:
            tried = " → ".join(q.value for q in QUALITY_ORDER)
            log.warning("  [%s] Not found at any quality (%s)", product.upper(), tried)

        results[product] = probe

    _print_summary(results)
    return results


# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------

_COL_PROD = 8
_COL_QUAL = 7
_COL_FILE = 52


def _print_summary(results: dict[str, ProbeResult]) -> None:
    """Print a formatted ASCII table of query results to stdout."""
    separator = "=" * 80
    print(
        f"\n{separator}\n"
        f"  Wuhan IGS FTP — Highest Quality Products\n"
        f"  Date: {DATE}  |  DOY: {DOY:03d}  |  GPS Week: {GPS_WEEK}\n"
        f"  Server: ftp://igs.gnsswhu.cn\n"
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
    for probe in results.values():
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


class TestWuhanFTPHighestQuality:
    """
    Integration tests against the Wuhan IGS FTP server.

    Each test validates a single product type in isolation so failures are
    immediately identifiable by test name.  All tests share the
    ``product_results`` module-scoped fixture so the FTP server is contacted
    only once per session.

    Requires live network access.  Skip offline::

        pytest -m "not integration"
    """

    def test_sp3_found_at_high_quality(self, product_results: dict) -> None:
        """SP3 (precise orbit) must be present at FINAL or RAPID quality."""
        probe = product_results["sp3"]
        days_past = (datetime.date.today() - DATE).days

        assert probe.found, (
            f"SP3 not found for {DATE} (DOY {DOY:03d}, GPS week {GPS_WEEK}). "
            f"Errors: {probe.errors or 'none — FTP listing returned no match'}."
        )
        assert probe.quality in (ProductQuality.FINAL, ProductQuality.RAPID), (
            f"SP3 found only at {probe.quality_label}; expected FINAL or RAPID "
            f"for a date {days_past} days in the past."
        )

    def test_clk_found_at_high_quality(self, product_results: dict) -> None:
        """CLK (precise clock) must be present at FINAL or RAPID quality."""
        probe = product_results["clk"]
        days_past = (datetime.date.today() - DATE).days

        assert probe.found, (
            f"CLK not found for {DATE} (DOY {DOY:03d}, GPS week {GPS_WEEK}). "
            f"Errors: {probe.errors or 'none — FTP listing returned no match'}."
        )
        assert probe.quality in (ProductQuality.FINAL, ProductQuality.RAPID), (
            f"CLK found only at {probe.quality_label}; expected FINAL or RAPID "
            f"for a date {days_past} days in the past."
        )

    def test_obx_found(self, product_results: dict) -> None:
        """OBX (satellite attitude quaternions) must be present for FINAL periods."""
        probe = product_results["obx"]
        assert probe.found, (
            f"OBX not found for {DATE} (DOY {DOY:03d}). "
            f"Errors: {probe.errors or 'none — FTP listing returned no match'}. "
            "Verify the OBX directory path and regex in Group1FileRegex."
        )

    def test_erp_found(self, product_results: dict) -> None:
        """ERP (earth rotation parameters) must be present at any quality."""
        probe = product_results["erp"]
        assert probe.found, (
            f"ERP not found for {DATE} (DOY {DOY:03d}). "
            f"Errors: {probe.errors or 'none — FTP listing returned no match'}. "
            "Verify the ERP directory path and regex in Group1FileRegex."
        )

    def test_found_products_have_valid_filenames(self, product_results: dict) -> None:
        """Every product that resolved must have a non-empty, extension-bearing filename."""
        for product, probe in product_results.items():
            if not probe.found:
                continue
            assert probe.filename, (
                f"{product.upper()} result has an empty filename."
            )
            assert "." in probe.filename, (
                f"{product.upper()} filename '{probe.filename}' has no file extension."
            )

    def test_found_products_have_valid_ftp_urls(self, product_results: dict) -> None:
        """Every product that resolved must produce a well-formed FTP URL."""
        for product, probe in product_results.items():
            if not probe.found:
                continue
            assert probe.url.startswith("ftp://"), (
                f"{product.upper()} URL '{probe.url}' does not start with 'ftp://'."
            )
            assert probe.filename in probe.url, (
                f"{product.upper()} URL '{probe.url}' does not contain its filename."
            )
