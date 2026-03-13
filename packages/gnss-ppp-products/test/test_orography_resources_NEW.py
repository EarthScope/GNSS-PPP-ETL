"""
Tests: Orography products via GNSSCenterConfig (VMF).

Load the VMF center config—HTTPS server—and verify that
OrographyFileQuery objects build correctly.  Integration tests probe
the VMF server to find actual orography grid files.

Products tested : Orography grids (1x1, 5x5)
Server          : vmf_https  (https://vmf.geo.tuwien.ac.at)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from gnss_ppp_products.assets.center.config import GNSSCenterConfig
from gnss_ppp_products.assets.orography.query import OrographyFileQuery
from gnss_ppp_products.assets.server.config import ServerProtocol
from gnss_ppp_products.server.products import process_product_query

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CONFIG_DIR = Path(__file__).resolve().parent.parent / "src" / "gnss_ppp_products" / "assets" / "config_files"


@pytest.fixture(scope="module")
def vmf_center() -> GNSSCenterConfig:
    return GNSSCenterConfig.from_yaml(CONFIG_DIR / "vmf.yaml")


@pytest.fixture(scope="module")
def orography_queries(vmf_center) -> list[OrographyFileQuery]:
    return vmf_center.build_orography_queries()


# ---------------------------------------------------------------------------
# Unit: Config → Query expansion
# ---------------------------------------------------------------------------


class TestOrographyQueryExpansion:
    """Verify that VMF center config expands orography queries (static, no date)."""

    def test_queries_returned(self, orography_queries) -> None:
        assert len(orography_queries) > 0

    def test_query_types(self, orography_queries) -> None:
        for q in orography_queries:
            assert isinstance(q, OrographyFileQuery)

    def test_server_attached(self, orography_queries) -> None:
        for q in orography_queries:
            assert q.server is not None
            assert q.server.id == "vmf_https"

    def test_server_protocol_is_https(self, orography_queries) -> None:
        for q in orography_queries:
            assert q.server.protocol == ServerProtocol.HTTPS

    def test_filenames_contain_orography(self, orography_queries) -> None:
        for q in orography_queries:
            assert "orography_ell" in q.filename

    def test_resolution_coverage(self, orography_queries) -> None:
        filenames = {q.filename for q in orography_queries}
        assert any("1x1" in f for f in filenames)
        assert any("5x5" in f for f in filenames)

    def test_directory(self, orography_queries) -> None:
        for q in orography_queries:
            assert q.directory == "station_coord_files"


# ---------------------------------------------------------------------------
# Integration: Probe VMF HTTPS server
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestOrographyHTTPSProbe:
    """Probe VMF HTTPS server to find actual orography grid files."""

    @pytest.fixture(scope="class")
    def probe_results(self, orography_queries) -> list[OrographyFileQuery]:
        target = next((q for q in orography_queries if "1x1" in q.filename), None)
        assert target is not None, "No 1x1 orography query found"
        return process_product_query(target)

    def test_found_files(self, probe_results) -> None:
        assert len(probe_results) > 0, "No files found on VMF HTTPS server"

    def test_filename_matches(self, probe_results) -> None:
        for result in probe_results:
            assert "orography_ell" in result.filename

    def test_server_preserved(self, probe_results) -> None:
        for result in probe_results:
            assert result.server is not None
            assert result.server.protocol == ServerProtocol.HTTPS
