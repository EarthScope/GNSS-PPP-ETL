"""
Integration test suite: Atmospheric correction products from FTP sources.

Metadata
--------
Date under test : 2025-01-01  (DOY 001)
Products probed : GIM (ionosphere), VMF1/VMF3 (troposphere)
Servers         : CODE (ftp.aiub.unibe.ch), VMF (vmf.geo.tuwien.ac.at)

Usage
-----
Run all integration tests::

    uv run pytest test/test_atmospheric_resources.py -v

Skip in offline environments::

    uv run pytest -m "not integration"
"""
from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass, field
from typing import Optional

import pytest

from gnss_ppp_products.resources.troposphere_resources import (
    AtmosphericProductQuality,
    AtmosphericFileResult,
    CODEGIMProductSource,
    VMFProductSource,
    AtmosphericProductSource,
)

log = logging.getLogger(__name__)

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Test parameters
# ---------------------------------------------------------------------------

DATE = datetime.date(2025, 1, 1)
DOY: int = DATE.timetuple().tm_yday  # 1

GIM_QUALITY_ORDER: list[AtmosphericProductQuality] = [
    AtmosphericProductQuality.FINAL,
    AtmosphericProductQuality.RAPID,
    AtmosphericProductQuality.PREDICTED,
]

VMF_HOURS: list[int] = [0, 6, 12, 18]


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------


@dataclass
class GIMProbeResult:
    """Outcome of querying a GIM product at a specific quality level."""

    quality: AtmosphericProductQuality
    file_result: Optional[AtmosphericFileResult] = None
    error: Optional[str] = None

    @property
    def found(self) -> bool:
        return self.file_result is not None

    @property
    def quality_label(self) -> str:
        return self.quality.value

    @property
    def filename(self) -> str:
        return self.file_result.filename if self.file_result else "not found"

    @property
    def url(self) -> str:
        return self.file_result.url if self.file_result else "—"


@dataclass
class VMFProbeResult:
    """Outcome of querying a VMF product."""

    product_type: str  # vmf1 or vmf3
    hour: Optional[int]
    file_result: Optional[AtmosphericFileResult] = None
    error: Optional[str] = None

    @property
    def found(self) -> bool:
        return self.file_result is not None

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
def gim_results() -> dict[str, GIMProbeResult]:
    """
    Query CODE FTP for GIM products at each quality level.

    Returns:
        dict mapping quality.value → GIMProbeResult
    """
    source = CODEGIMProductSource()
    results: dict[str, GIMProbeResult] = {}

    log.info("Probing CODE FTP for GIM — %s (DOY %03d)", DATE, DOY)

    for quality in GIM_QUALITY_ORDER:
        probe = GIMProbeResult(quality=quality)
        try:
            file_result = source.query(DATE, quality)
        except Exception as exc:
            probe.error = str(exc)
            log.warning("  [GIM] %s — ERROR: %s", quality.value, exc)
            file_result = None

        if file_result is not None:
            probe.file_result = file_result
            log.info("  [GIM] Found at %s — %s", quality.value, file_result.filename)
        else:
            log.warning("  [GIM] Not found at %s", quality.value)

        results[quality.value] = probe

    _print_gim_summary(source.directory_source.ftpserver, results)
    return results


@pytest.fixture(scope="module")
def vmf_results() -> dict[str, list[VMFProbeResult]]:
    """
    Query VMF FTP for VMF1 and VMF3 products.

    Returns:
        dict mapping product_type → list of VMFProbeResult per hour
    """
    source = VMFProductSource()
    results: dict[str, list[VMFProbeResult]] = {"vmf1": [], "vmf3": []}

    log.info("Probing VMF FTP — %s (DOY %03d)", DATE, DOY)

    for product_type in ["vmf1", "vmf3"]:
        for hour in VMF_HOURS:
            probe = VMFProbeResult(product_type=product_type, hour=hour)
            try:
                if product_type == "vmf1":
                    file_result = source.query_vmf1(DATE, hour)
                else:
                    file_result = source.query_vmf3(DATE, hour)
            except Exception as exc:
                probe.error = str(exc)
                log.warning("  [%s] H%02d — ERROR: %s", product_type.upper(), hour, exc)
                file_result = None

            if file_result is not None:
                probe.file_result = file_result
                log.info(
                    "  [%s] H%02d — %s",
                    product_type.upper(),
                    hour,
                    file_result.filename,
                )

            results[product_type].append(probe)

    _print_vmf_summary(source.directory_source.ftpserver, results)
    return results


@pytest.fixture(scope="module")
def unified_results() -> dict[str, Optional[AtmosphericFileResult]]:
    """
    Test the unified AtmosphericProductSource interface.

    Returns:
        dict with gim and vmf results
    """
    source = AtmosphericProductSource()
    results: dict[str, Optional[AtmosphericFileResult]] = {}

    log.info("Probing via AtmosphericProductSource — %s (DOY %03d)", DATE, DOY)

    # GIM with fallback
    try:
        results["gim"] = source.query_gim(DATE, fallback=True)
    except Exception as exc:
        log.warning("  [UNIFIED] GIM — ERROR: %s", exc)
        results["gim"] = None

    # VMF1
    try:
        results["vmf1"] = source.query_vmf(DATE, version="vmf1", hour=0)
    except Exception as exc:
        log.warning("  [UNIFIED] VMF1 — ERROR: %s", exc)
        results["vmf1"] = None

    # VMF3
    try:
        results["vmf3"] = source.query_vmf(DATE, version="vmf3", hour=0)
    except Exception as exc:
        log.warning("  [UNIFIED] VMF3 — ERROR: %s", exc)
        results["vmf3"] = None

    return results


# ---------------------------------------------------------------------------
# Summary tables
# ---------------------------------------------------------------------------

_COL_PROD = 10
_COL_QUAL = 12
_COL_FILE = 40


def _print_gim_summary(ftpserver: str, results: dict[str, GIMProbeResult]) -> None:
    """Print summary table for GIM results."""
    separator = "=" * 80
    print(
        f"\n{separator}\n"
        f"  CODE FTP — GIM Ionosphere Products\n"
        f"  Date: {DATE}  |  DOY: {DOY:03d}\n"
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
        f"  {'-'*50}"
    )
    for quality_val, probe in results.items():
        status = "✓" if probe.found else "✗"
        print(
            f"  {status} GIM      "
            f"  {probe.quality_label:<{_COL_QUAL}}"
            f"  {probe.filename:<{_COL_FILE}}"
            f"  {probe.url}"
        )
        if probe.error:
            print(f"    ERROR: {probe.error}")

    print(f"{separator}\n")


def _print_vmf_summary(ftpserver: str, results: dict[str, list[VMFProbeResult]]) -> None:
    """Print summary table for VMF results."""
    separator = "=" * 80
    print(
        f"\n{separator}\n"
        f"  VMF Vienna — Troposphere Products\n"
        f"  Date: {DATE}  |  DOY: {DOY:03d}\n"
        f"  Server: {ftpserver}\n"
        f"{separator}"
    )
    print(
        f"  {'Product':<{_COL_PROD}}"
        f"  {'Hour':<6}"
        f"  {'Filename':<{_COL_FILE}}"
        f"  FTP URL"
    )
    print(
        f"  {'-'*_COL_PROD}"
        f"  {'-'*6}"
        f"  {'-'*_COL_FILE}"
        f"  {'-'*50}"
    )
    for product_type, probes in results.items():
        for probe in probes:
            status = "✓" if probe.found else "✗"
            hour_str = f"H{probe.hour:02d}" if probe.hour is not None else "—"
            print(
                f"  {status} {product_type.upper():<8}"
                f"  {hour_str:<6}"
                f"  {probe.filename:<{_COL_FILE}}"
                f"  {probe.url}"
            )
            if probe.error:
                print(f"    ERROR: {probe.error}")

    print(f"{separator}\n")


# ---------------------------------------------------------------------------
# Integration tests — GIM
# ---------------------------------------------------------------------------


class TestCODEGIMProducts:
    """
    Integration tests for CODE GIM ionosphere products.

    Requires live network access. Skip offline::

        pytest -m "not integration"
    """

    def test_gim_found_at_any_quality(self, gim_results: dict[str, GIMProbeResult]) -> None:
        """At least one GIM product must be available for the test date."""
        found_any = any(probe.found for probe in gim_results.values())
        assert found_any, (
            f"GIM not found at any quality level for {DATE}. "
            f"Tried: {', '.join(q.value for q in GIM_QUALITY_ORDER)}."
        )

    def test_gim_final_preferred(self, gim_results: dict[str, GIMProbeResult]) -> None:
        """FINAL GIM should be available for dates > 2 weeks old."""
        days_past = (datetime.date.today() - DATE).days
        if days_past < 14:
            pytest.skip("Date too recent for FINAL GIM expectation")

        final_probe = gim_results.get(AtmosphericProductQuality.FINAL.value)
        assert final_probe is not None and final_probe.found, (
            f"FINAL GIM not found for {DATE} ({days_past} days old). "
            "Expected FINAL quality for dates > 2 weeks old."
        )

    def test_gim_has_valid_filename(self, gim_results: dict[str, GIMProbeResult]) -> None:
        """Found GIM products must have valid IONEX-like filenames."""
        for probe in gim_results.values():
            if not probe.found:
                continue
            assert probe.filename, "GIM result has empty filename"
            # IONEX files typically end in .Z or have I in extension
            assert "." in probe.filename, (
                f"GIM filename '{probe.filename}' has no extension"
            )

    def test_gim_has_valid_url(self, gim_results: dict[str, GIMProbeResult]) -> None:
        """Found GIM products must have valid FTP URLs."""
        for probe in gim_results.values():
            if not probe.found:
                continue
            assert probe.url.startswith("ftp://"), (
                f"GIM URL '{probe.url}' does not start with 'ftp://'"
            )
            assert probe.filename in probe.url, (
                f"GIM URL '{probe.url}' does not contain filename"
            )


# ---------------------------------------------------------------------------
# Integration tests — VMF
# ---------------------------------------------------------------------------


#@pytest.mark.skip(reason="VMF server often unreachable/slow - run manually when needed")
class TestVMFProducts:
    """
    Integration tests for VMF troposphere products.

    Requires live network access. Skip offline::

        pytest -m "not integration"
        
    Note: VMF server (vmf.geo.tuwien.ac.at) is often slow or unreachable.
    These tests are skipped by default - run manually with::
    
        pytest test/test_atmospheric_resources.py::TestVMFProducts -v --no-header
    """

    def test_vmf1_found_for_at_least_one_hour(
        self, vmf_results: dict[str, list[VMFProbeResult]]
    ) -> None:
        """At least one VMF1 hourly file must be available."""
        vmf1_probes = vmf_results.get("vmf1", [])
        found_any = any(probe.found for probe in vmf1_probes)
        assert found_any, (
            f"VMF1 not found for any hour on {DATE}. "
            f"Tried hours: {VMF_HOURS}."
        )

    def test_vmf3_found_for_at_least_one_hour(
        self, vmf_results: dict[str, list[VMFProbeResult]]
    ) -> None:
        """At least one VMF3 hourly file must be available."""
        vmf3_probes = vmf_results.get("vmf3", [])
        found_any = any(probe.found for probe in vmf3_probes)
        assert found_any, (
            f"VMF3 not found for any hour on {DATE}. "
            f"Tried hours: {VMF_HOURS}."
        )

    def test_vmf_has_valid_filenames(
        self, vmf_results: dict[str, list[VMFProbeResult]]
    ) -> None:
        """Found VMF products must have valid filenames."""
        for product_type, probes in vmf_results.items():
            for probe in probes:
                if not probe.found:
                    continue
                assert probe.filename, (
                    f"{product_type.upper()} H{probe.hour:02d} has empty filename"
                )
                # VMF files contain year+doy in name
                assert str(DATE.year) in probe.filename or str(DOY) in probe.filename, (
                    f"{product_type.upper()} filename '{probe.filename}' "
                    "doesn't contain date identifiers"
                )

    def test_vmf_has_valid_urls(
        self, vmf_results: dict[str, list[VMFProbeResult]]
    ) -> None:
        """Found VMF products must have valid FTP URLs."""
        for product_type, probes in vmf_results.items():
            for probe in probes:
                if not probe.found:
                    continue
                assert probe.url.startswith("ftp://"), (
                    f"{product_type.upper()} URL '{probe.url}' "
                    "does not start with 'ftp://'"
                )


# ---------------------------------------------------------------------------
# Integration tests — Unified interface
# ---------------------------------------------------------------------------


class TestUnifiedAtmosphericSource:
    """
    Integration tests for the unified AtmosphericProductSource interface.
    """

    def test_unified_gim_query(
        self, unified_results: dict[str, Optional[AtmosphericFileResult]]
    ) -> None:
        """Unified GIM query with fallback should find a product."""
        gim = unified_results.get("gim")
        assert gim is not None, (
            f"Unified GIM query failed for {DATE}. "
            "Expected at least one quality level to succeed."
        )
        assert gim.product_type == "gim"

    #@pytest.mark.skip(reason="VMF server often unreachable - run manually")
    def test_unified_vmf1_query(
        self, unified_results: dict[str, Optional[AtmosphericFileResult]]
    ) -> None:
        """Unified VMF1 query should find a product."""
        vmf1 = unified_results.get("vmf1")
        assert vmf1 is not None, f"Unified VMF1 query failed for {DATE}"
        assert vmf1.product_type == "vmf1"

    #@pytest.mark.skip(reason="VMF server often unreachable - run manually")
    def test_unified_vmf3_query(
        self, unified_results: dict[str, Optional[AtmosphericFileResult]]
    ) -> None:
        """Unified VMF3 query should find a product."""
        vmf3 = unified_results.get("vmf3")
        assert vmf3 is not None, f"Unified VMF3 query failed for {DATE}"
        assert vmf3.product_type == "vmf3"
