"""
Tests: Orbit/Clock products via GNSSCenterConfig.

Load center configs for Wuhan (FTP), IGS (FTP), and CODE (FTP),
then verify that ProductFileQuery objects for orbit/clock products
build correctly.  Integration tests probe each server.

Products tested : SP3, CLK, ERP, BIA, OBX
Servers         : wuhan_ftp, ign_ftp, code_ftp
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
GPS_WEEK = (DATE - datetime.date(1980, 1, 6)).days // 7  # 2347


@pytest.fixture(scope="module")
def wuhan_center() -> GNSSCenterConfig:
    return GNSSCenterConfig.from_yaml(CONFIG_DIR / "wuhan.yaml")


@pytest.fixture(scope="module")
def igs_center() -> GNSSCenterConfig:
    return GNSSCenterConfig.from_yaml(CONFIG_DIR / "igs.yaml")


@pytest.fixture(scope="module")
def code_center() -> GNSSCenterConfig:
    return GNSSCenterConfig.from_yaml(CONFIG_DIR / "code.yaml")


def _orbit_queries(center: GNSSCenterConfig) -> list[ProductFileQuery]:
    """All product queries (orbit, clock, erp, bias, obx) excluding GIM."""
    return [q for q in center.build_product_queries(DATE) if "GIM" not in (q.filename or "")]


@pytest.fixture(scope="module")
def wuhan_orbit_queries(wuhan_center) -> list[ProductFileQuery]:
    return _orbit_queries(wuhan_center)


@pytest.fixture(scope="module")
def igs_orbit_queries(igs_center) -> list[ProductFileQuery]:
    return _orbit_queries(igs_center)


@pytest.fixture(scope="module")
def code_orbit_queries(code_center) -> list[ProductFileQuery]:
    return _orbit_queries(code_center)


# ---------------------------------------------------------------------------
# Unit: Wuhan Orbit/Clock (FTP)
# ---------------------------------------------------------------------------


class TestWuhanOrbitExpansion:
    """Verify Wuhan center config produces orbit/clock product queries."""

    def test_queries_returned(self, wuhan_orbit_queries) -> None:
        assert len(wuhan_orbit_queries) > 0

    def test_query_types(self, wuhan_orbit_queries) -> None:
        for q in wuhan_orbit_queries:
            assert isinstance(q, ProductFileQuery)

    def test_server_attached(self, wuhan_orbit_queries) -> None:
        for q in wuhan_orbit_queries:
            assert q.server is not None
            assert q.server.id == "wuhan_ftp"

    def test_server_protocol_is_ftp(self, wuhan_orbit_queries) -> None:
        for q in wuhan_orbit_queries:
            assert q.server.protocol == ServerProtocol.FTP

    def test_sp3_present(self, wuhan_orbit_queries) -> None:
        sp3 = [q for q in wuhan_orbit_queries if "SP3" in q.filename]
        assert len(sp3) > 0

    def test_clk_present(self, wuhan_orbit_queries) -> None:
        clk = [q for q in wuhan_orbit_queries if "CLK" in q.filename]
        assert len(clk) > 0

    def test_erp_present(self, wuhan_orbit_queries) -> None:
        erp = [q for q in wuhan_orbit_queries if "ERP" in q.filename]
        assert len(erp) > 0

    def test_bias_present(self, wuhan_orbit_queries) -> None:
        bia = [q for q in wuhan_orbit_queries if "BIA" in q.filename]
        assert len(bia) > 0

    def test_obx_present(self, wuhan_orbit_queries) -> None:
        obx = [q for q in wuhan_orbit_queries if "OBX" in q.filename]
        assert len(obx) > 0

    def test_directories_contain_year(self, wuhan_orbit_queries) -> None:
        for q in wuhan_orbit_queries:
            assert "2025" in q.directory

    def test_filename_contains_wum_or_wmc(self, wuhan_orbit_queries) -> None:
        centers = {q.filename[:3] for q in wuhan_orbit_queries}
        assert centers & {"WUM", "WMC"}, f"Expected WUM/WMC, got {centers}"

    def test_quality_expansion(self, wuhan_orbit_queries) -> None:
        """Both FIN and RAP should appear."""
        filenames = " ".join(q.filename for q in wuhan_orbit_queries)
        assert "FIN" in filenames
        assert "RAP" in filenames


# ---------------------------------------------------------------------------
# Unit: IGS Orbit/Clock (FTP via IGN)
# ---------------------------------------------------------------------------


class TestIGSOrbitExpansion:
    """Verify IGS center config produces orbit/clock queries."""

    def test_queries_returned(self, igs_orbit_queries) -> None:
        assert len(igs_orbit_queries) > 0

    def test_server_protocol_is_ftp(self, igs_orbit_queries) -> None:
        for q in igs_orbit_queries:
            assert q.server.protocol == ServerProtocol.FTP

    def test_directory_contains_gps_week(self, igs_orbit_queries) -> None:
        for q in igs_orbit_queries:
            assert str(GPS_WEEK) in q.directory

    def test_filename_contains_igs(self, igs_orbit_queries) -> None:
        for q in igs_orbit_queries:
            assert "IGS" in q.filename


# ---------------------------------------------------------------------------
# Unit: CODE Orbit/Clock (FTP)
# ---------------------------------------------------------------------------


class TestCODEOrbitExpansion:
    """Verify CODE center config produces orbit/clock queries."""

    def test_queries_returned(self, code_orbit_queries) -> None:
        assert len(code_orbit_queries) > 0

    def test_server_protocol_is_ftp(self, code_orbit_queries) -> None:
        for q in code_orbit_queries:
            assert q.server.protocol == ServerProtocol.FTP

    def test_directory_contains_year(self, code_orbit_queries) -> None:
        for q in code_orbit_queries:
            assert "2025" in q.directory

    def test_filename_contains_cod(self, code_orbit_queries) -> None:
        for q in code_orbit_queries:
            assert "COD" in q.filename


# ---------------------------------------------------------------------------
# Integration: Probe Wuhan FTP for SP3
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestWuhanOrbitFTPProbe:
    """Probe Wuhan FTP for SP3 orbit files."""

    @pytest.fixture(scope="class")
    def probe_results(self, wuhan_orbit_queries) -> list[ProductFileQuery]:
        target = next(
            (q for q in wuhan_orbit_queries if "SP3" in q.filename and "WUM" in q.filename and "FIN" in q.filename and "05M" in q.filename),
            None,
        )
        assert target is not None, "No Wuhan SP3 WUM FIN 05M query found"
        return process_product_query(target)

    def test_found_files(self, probe_results) -> None:
        assert len(probe_results) > 0, "No SP3 files found on Wuhan FTP"

    def test_filename_contains_sp3(self, probe_results) -> None:
        for result in probe_results:
            assert "SP3" in result.filename or result.filename.endswith(".SP3.gz")

    def test_server_preserved(self, probe_results) -> None:
        for result in probe_results:
            assert result.server.protocol == ServerProtocol.FTP


# ---------------------------------------------------------------------------
# Integration: Probe IGS/IGN FTP for SP3
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestIGSOrbitFTPProbe:
    """Probe IGS (IGN France) FTP for SP3 orbit files."""

    @pytest.fixture(scope="class")
    def probe_results(self, igs_orbit_queries) -> list[ProductFileQuery]:
        target = next(
            (q for q in igs_orbit_queries if q.format.value == "SP3" and "IGS" in q.filename.upper()),
            None,
        )
        assert target is not None, "No IGS SP3 FIN query found"
        return process_product_query(target)

    def test_found_files(self, probe_results) -> None:
        assert len(probe_results) > 0, "No SP3 files found on IGS FTP"

    def test_server_preserved(self, probe_results) -> None:
        for result in probe_results:
            assert result.server.protocol == ServerProtocol.FTP


# ---------------------------------------------------------------------------
# Integration: Probe CODE FTP for SP3
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestCODEOrbitFTPProbe:
    """Probe CODE FTP for SP3 orbit files."""

    @pytest.fixture(scope="class")
    def probe_results(self, code_orbit_queries) -> list[ProductFileQuery]:
        target = next(
            (q for q in code_orbit_queries if "SP3" in q.filename and "FIN" in q.filename),
            None,
        )
        assert target is not None, "No CODE SP3 FIN query found"
        return process_product_query(target)

    def test_found_files(self, probe_results) -> None:
        assert len(probe_results) > 0, "No SP3 files found on CODE FTP"

    def test_server_preserved(self, probe_results) -> None:
        for result in probe_results:
            assert result.server.protocol == ServerProtocol.FTP
