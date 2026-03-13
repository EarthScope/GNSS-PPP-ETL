"""
Tests: Troposphere products via GNSSCenterConfig (VMF).

Load the VMF center config from YAML—which uses an HTTPS server—and
verify that TroposphereFileQuery objects build correctly.  Integration
tests probe the VMF HTTP server to locate actual files.

Products tested : VMF1, VMF3 (Vienna Mapping Functions)
Server          : vmf_https  (https://vmf.geo.tuwien.ac.at)
"""
from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from gnss_ppp_products.assets.center.config import GNSSCenterConfig
from gnss_ppp_products.assets.troposphere.query import TroposphereFileQuery
from gnss_ppp_products.assets.server.config import ServerProtocol
from gnss_ppp_products.server.products import process_product_query

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CONFIG_DIR = Path(__file__).resolve().parent.parent / "src" / "gnss_ppp_products" / "assets" / "config_files"
DATE = datetime.date(2025, 1, 1)


@pytest.fixture(scope="module")
def vmf_center() -> GNSSCenterConfig:
    return GNSSCenterConfig.from_yaml(CONFIG_DIR / "vmf.yaml")


@pytest.fixture(scope="module")
def troposphere_queries(vmf_center) -> list[TroposphereFileQuery]:
    return vmf_center.build_troposphere_queries(DATE)


# ---------------------------------------------------------------------------
# Unit: Config → Query expansion
# ---------------------------------------------------------------------------


class TestTroposphereQueryExpansion:
    """Verify that VMF center config expands into expected troposphere queries."""

    def test_queries_returned(self, troposphere_queries) -> None:
        assert len(troposphere_queries) > 0

    def test_query_types(self, troposphere_queries) -> None:
        for q in troposphere_queries:
            assert isinstance(q, TroposphereFileQuery)

    def test_server_attached(self, troposphere_queries) -> None:
        for q in troposphere_queries:
            assert q.server is not None
            assert q.server.id == "vmf_https"

    def test_server_protocol_is_https(self, troposphere_queries) -> None:
        for q in troposphere_queries:
            assert q.server.protocol == ServerProtocol.HTTPS

    def test_vmf3_filenames_present(self, troposphere_queries) -> None:
        vmf3 = [q for q in troposphere_queries if "VMF3" in q.filename]
        assert len(vmf3) > 0

    def test_vmf1_filenames_use_vmfg(self, troposphere_queries) -> None:
        """VMF1 products should map to VMFG in filenames."""
        vmf1 = [q for q in troposphere_queries if "VMFG" in q.filename]
        assert len(vmf1) > 0

    def test_directories_contain_year(self, troposphere_queries) -> None:
        for q in troposphere_queries:
            assert "2025" in q.directory

    def test_hour_coverage(self, troposphere_queries) -> None:
        """All four hours should appear across queries."""
        hours = {q.filename.split(".")[-1] for q in troposphere_queries}
        assert hours >= {"H00", "H06", "H12", "H18"}

    def test_resolution_coverage(self, troposphere_queries) -> None:
        dirs = {q.directory for q in troposphere_queries}
        has_1x1 = any("1x1" in d for d in dirs)
        has_5x5 = any("5x5" in d for d in dirs)
        assert has_1x1 or has_5x5, "Expected at least one resolution in queries"


# ---------------------------------------------------------------------------
# Integration: Probe VMF HTTPS server
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestTroposphereHTTPSProbe:
    """Probe VMF HTTPS server to find actual troposphere files."""

    @pytest.fixture(scope="class")
    def probe_results(self, troposphere_queries) -> list[TroposphereFileQuery]:
        """Probe the first VMF3 1x1 H00 query."""
        target = next(
            (q for q in troposphere_queries if "VMF3" in q.filename and "1x1" in q.directory and "H00" in q.filename),
            None,
        )
        assert target is not None, "No VMF3 1x1 H00 query found"
        return process_product_query(target)

    def test_found_files(self, probe_results) -> None:
        assert len(probe_results) > 0, "No files found on VMF HTTPS server"

    def test_filename_matches(self, probe_results) -> None:
        for result in probe_results:
            assert "VMF3" in result.filename

    def test_server_preserved(self, probe_results) -> None:
        for result in probe_results:
            assert result.server is not None
            assert result.server.protocol == ServerProtocol.HTTPS
