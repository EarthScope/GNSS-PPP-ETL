"""
Tests: Ionosphere (GIM) products via GNSSCenterConfig.

Load center configs for CODE (FTP), Wuhan (FTP), and CDDIS (FTPS),
then verify that ProductFileQuery objects for GIM ionosphere maps
build correctly.  Integration tests probe each server.

Products tested : GIM (Global Ionosphere Maps) in INX format
Servers         : code_ftp, wuhan_ftp, cddis_ftps
"""
from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from gnss_ppp_products.assets.center.config import GNSSCenterConfig
from gnss_ppp_products.assets.products.query import ProductFileQuery
from gnss_ppp_products.assets.server.config import ServerProtocol
from gnss_ppp_products.server.products import process_product_query

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CONFIG_DIR = Path(__file__).resolve().parent.parent / "src" / "gnss_ppp_products" / "assets" / "config_files"
DATE = datetime.date(2025, 1, 1)


@pytest.fixture(scope="module")
def code_center() -> GNSSCenterConfig:
    return GNSSCenterConfig.from_yaml(CONFIG_DIR / "code.yaml")


@pytest.fixture(scope="module")
def wuhan_center() -> GNSSCenterConfig:
    return GNSSCenterConfig.from_yaml(CONFIG_DIR / "wuhan.yaml")


@pytest.fixture(scope="module")
def cddis_center() -> GNSSCenterConfig:
    return GNSSCenterConfig.from_yaml(CONFIG_DIR / "cddis.yaml")


def _gim_queries(center: GNSSCenterConfig) -> list[ProductFileQuery]:
    """Filter product queries to only GIM content."""
    return [q for q in center.build_product_queries(DATE) if "GIM" in (q.filename or "")]


@pytest.fixture(scope="module")
def code_gim_queries(code_center) -> list[ProductFileQuery]:
    return _gim_queries(code_center)


@pytest.fixture(scope="module")
def wuhan_gim_queries(wuhan_center) -> list[ProductFileQuery]:
    return _gim_queries(wuhan_center)


@pytest.fixture(scope="module")
def cddis_gim_queries(cddis_center) -> list[ProductFileQuery]:
    return _gim_queries(cddis_center)


# ---------------------------------------------------------------------------
# Unit: CODE GIM queries (FTP)
# ---------------------------------------------------------------------------


class TestCODEGIMExpansion:
    """Verify CODE center config produces GIM queries."""

    def test_queries_returned(self, code_gim_queries) -> None:
        assert len(code_gim_queries) > 0

    def test_query_types(self, code_gim_queries) -> None:
        for q in code_gim_queries:
            assert isinstance(q, ProductFileQuery)

    def test_server_attached(self, code_gim_queries) -> None:
        for q in code_gim_queries:
            assert q.server is not None
            assert q.server.id == "code_ftp"

    def test_server_protocol_is_ftp(self, code_gim_queries) -> None:
        for q in code_gim_queries:
            assert q.server.protocol == ServerProtocol.FTP

    def test_filename_contains_gim(self, code_gim_queries) -> None:
        for q in code_gim_queries:
            assert "GIM" in q.filename

    def test_directory_contains_year(self, code_gim_queries) -> None:
        for q in code_gim_queries:
            assert "2025" in q.directory


# ---------------------------------------------------------------------------
# Unit: Wuhan GIM queries (FTP)
# ---------------------------------------------------------------------------


class TestWuhanGIMExpansion:
    """Verify Wuhan center config produces GIM queries over FTP."""

    def test_queries_returned(self, wuhan_gim_queries) -> None:
        assert len(wuhan_gim_queries) > 0

    def test_server_protocol_is_ftp(self, wuhan_gim_queries) -> None:
        for q in wuhan_gim_queries:
            assert q.server.protocol == ServerProtocol.FTP

    def test_directory_ionex_path(self, wuhan_gim_queries) -> None:
        for q in wuhan_gim_queries:
            assert "ionex" in q.directory

    def test_multiple_centers_in_filenames(self, wuhan_gim_queries) -> None:
        """Wuhan mirrors GIM from COD, IGS, JPL."""
        centers = {q.filename[:3] for q in wuhan_gim_queries}
        assert len(centers) >= 2, f"Expected multiple centers, got {centers}"


# ---------------------------------------------------------------------------
# Unit: CDDIS GIM queries (FTPS)
# ---------------------------------------------------------------------------


class TestCDDISGIMExpansion:
    """Verify CDDIS center config produces GIM queries over FTPS."""

    def test_queries_returned(self, cddis_gim_queries) -> None:
        assert len(cddis_gim_queries) > 0

    def test_server_protocol_is_ftps(self, cddis_gim_queries) -> None:
        for q in cddis_gim_queries:
            assert q.server.protocol == ServerProtocol.FTPS

    def test_directory_contains_ionex(self, cddis_gim_queries) -> None:
        for q in cddis_gim_queries:
            assert "ionex" in q.directory

    def test_filename_contains_gim(self, cddis_gim_queries) -> None:
        for q in cddis_gim_queries:
            assert "GIM" in q.filename


# ---------------------------------------------------------------------------
# Integration: Probe CODE FTP for GIM
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestCODEGIMFTPProbe:
    """Probe CODE FTP server for GIM files."""

    @pytest.fixture(scope="class")
    def probe_results(self, code_gim_queries) -> list[ProductFileQuery]:
        target = next(
            (q for q in code_gim_queries if "FIN" in q.filename and "01H" in q.filename),
            None,
        )
        assert target is not None, "No CODE GIM FIN 01H query found"
        return process_product_query(target)

    def test_found_files(self, probe_results) -> None:
        assert len(probe_results) > 0, "No GIM files found on CODE FTP"

    def test_filename_contains_gim(self, probe_results) -> None:
        for result in probe_results:
            assert "GIM" in result.filename

    def test_server_preserved(self, probe_results) -> None:
        for result in probe_results:
            assert result.server.protocol == ServerProtocol.FTP


# ---------------------------------------------------------------------------
# Integration: Probe Wuhan FTP for GIM
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestWuhanGIMFTPProbe:
    """Probe Wuhan FTP server for GIM files."""

    @pytest.fixture(scope="class")
    def probe_results(self, wuhan_gim_queries) -> list[ProductFileQuery]:
        target = next(
            (q for q in wuhan_gim_queries if "COD" in q.filename and "FIN" in q.filename),
            None,
        )
        assert target is not None, "No Wuhan GIM COD FIN query found"
        return process_product_query(target)

    def test_found_files(self, probe_results) -> None:
        assert len(probe_results) > 0, "No GIM files found on Wuhan FTP"

    def test_server_preserved(self, probe_results) -> None:
        for result in probe_results:
            assert result.server.protocol == ServerProtocol.FTP
