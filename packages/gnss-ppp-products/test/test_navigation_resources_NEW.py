"""
Tests: Navigation (broadcast ephemeris) products via GNSSCenterConfig.

Load center configs for Wuhan (FTP), CDDIS (FTPS), and IGS (FTP),
then verify that RinexFileQuery objects for broadcast navigation
build correctly.  Integration tests probe each server.

Products tested : RINEX3 broadcast navigation (BRDC)
Servers         : wuhan_ftp, cddis_ftps, ign_ftp
"""
from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from gnss_ppp_products.assets.center.config import GNSSCenterConfig
from gnss_ppp_products.assets.rinex.query import RinexFileQuery
from gnss_ppp_products.assets.server.config import ServerProtocol
from gnss_ppp_products.server.products import process_product_query

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CONFIG_DIR = Path(__file__).resolve().parent.parent / "src" / "gnss_ppp_products" / "assets" / "config_files"
DATE = datetime.date(2025, 1, 1)


@pytest.fixture(scope="module")
def wuhan_center() -> GNSSCenterConfig:
    return GNSSCenterConfig.from_yaml(CONFIG_DIR / "wuhan.yaml")


@pytest.fixture(scope="module")
def cddis_center() -> GNSSCenterConfig:
    return GNSSCenterConfig.from_yaml(CONFIG_DIR / "cddis.yaml")


@pytest.fixture(scope="module")
def igs_center() -> GNSSCenterConfig:
    return GNSSCenterConfig.from_yaml(CONFIG_DIR / "igs.yaml")


@pytest.fixture(scope="module")
def wuhan_nav_queries(wuhan_center) -> list[RinexFileQuery]:
    return wuhan_center.build_rinex_queries(DATE)


@pytest.fixture(scope="module")
def cddis_nav_queries(cddis_center) -> list[RinexFileQuery]:
    return cddis_center.build_rinex_queries(DATE)


@pytest.fixture(scope="module")
def igs_nav_queries(igs_center) -> list[RinexFileQuery]:
    return igs_center.build_rinex_queries(DATE)


# ---------------------------------------------------------------------------
# Unit: Wuhan Navigation (FTP)
# ---------------------------------------------------------------------------


class TestWuhanNavigationExpansion:
    """Verify Wuhan center config produces RINEX nav queries."""

    def test_queries_returned(self, wuhan_nav_queries) -> None:
        assert len(wuhan_nav_queries) > 0

    def test_query_types(self, wuhan_nav_queries) -> None:
        for q in wuhan_nav_queries:
            assert isinstance(q, RinexFileQuery)

    def test_server_attached(self, wuhan_nav_queries) -> None:
        for q in wuhan_nav_queries:
            assert q.server is not None
            assert q.server.id == "wuhan_ftp"

    def test_server_protocol_is_ftp(self, wuhan_nav_queries) -> None:
        for q in wuhan_nav_queries:
            assert q.server.protocol == ServerProtocol.FTP

    def test_filename_contains_brdc(self, wuhan_nav_queries) -> None:
        for q in wuhan_nav_queries:
            assert "BRDC" in q.filename

    def test_directory_contains_year(self, wuhan_nav_queries) -> None:
        for q in wuhan_nav_queries:
            assert "2025" in q.directory

    def test_satellite_system_expansion(self, wuhan_nav_queries) -> None:
        """Wuhan provides E (Galileo) and M (Mixed) navigation."""
        filenames = {q.filename for q in wuhan_nav_queries}
        assert any("EN" in f for f in filenames) or any("MN" in f for f in filenames)


# ---------------------------------------------------------------------------
# Unit: CDDIS Navigation (FTPS)
# ---------------------------------------------------------------------------


class TestCDDISNavigationExpansion:
    """Verify CDDIS center config produces RINEX nav queries over FTPS."""

    def test_queries_returned(self, cddis_nav_queries) -> None:
        assert len(cddis_nav_queries) > 0

    def test_server_protocol_is_ftps(self, cddis_nav_queries) -> None:
        for q in cddis_nav_queries:
            assert q.server.protocol == ServerProtocol.FTPS

    def test_directory_cddis_path(self, cddis_nav_queries) -> None:
        for q in cddis_nav_queries:
            assert "gnss/data/daily" in q.directory

    def test_filename_has_rnx(self, cddis_nav_queries) -> None:
        for q in cddis_nav_queries:
            assert ".rnx" in q.filename


# ---------------------------------------------------------------------------
# Unit: IGS Navigation (FTP via IGN)
# ---------------------------------------------------------------------------


class TestIGSNavigationExpansion:
    """Verify IGS center config produces RINEX nav queries over FTP."""

    def test_queries_returned(self, igs_nav_queries) -> None:
        assert len(igs_nav_queries) > 0

    def test_server_protocol_is_ftp(self, igs_nav_queries) -> None:
        for q in igs_nav_queries:
            assert q.server.protocol == ServerProtocol.FTP

    def test_directory_igs_path(self, igs_nav_queries) -> None:
        for q in igs_nav_queries:
            assert "pub/igs/data" in q.directory


# ---------------------------------------------------------------------------
# Integration: Probe Wuhan FTP for navigation
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestWuhanNavigationFTPProbe:
    """Probe Wuhan FTP for broadcast navigation files."""

    @pytest.fixture(scope="class")
    def probe_results(self, wuhan_nav_queries) -> list[RinexFileQuery]:
        target = next(
            (q for q in wuhan_nav_queries if "MN" in q.filename),
            None,
        )
        assert target is not None, "No Wuhan mixed-nav query found"
        return process_product_query(target)

    def test_found_files(self, probe_results) -> None:
        assert len(probe_results) > 0, "No nav files found on Wuhan FTP"

    def test_filename_contains_brdc(self, probe_results) -> None:
        for result in probe_results:
            assert "BRDC" in result.filename

    def test_server_preserved(self, probe_results) -> None:
        for result in probe_results:
            assert result.server.protocol == ServerProtocol.FTP


# ---------------------------------------------------------------------------
# Integration: Probe IGS/IGN FTP for navigation
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestIGSNavigationFTPProbe:
    """Probe IGS (IGN France) FTP for broadcast navigation files."""

    @pytest.fixture(scope="class")
    def probe_results(self, igs_nav_queries) -> list[RinexFileQuery]:
        target = igs_nav_queries[0] if igs_nav_queries else None
        assert target is not None, "No IGS nav query found"
        return process_product_query(target)

    def test_found_files(self, probe_results) -> None:
        assert len(probe_results) > 0, "No nav files found on IGS FTP"

    def test_server_preserved(self, probe_results) -> None:
        for result in probe_results:
            assert result.server.protocol == ServerProtocol.FTP
