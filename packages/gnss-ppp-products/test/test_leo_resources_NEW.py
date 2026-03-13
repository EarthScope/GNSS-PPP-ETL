"""
Tests: LEO satellite products (GRACE/GRACE-FO) via GNSSCenterConfig (GFZ).

Load the GFZ center config—FTP server—and verify that LEOFileQuery
objects build correctly.  Integration tests probe the GFZ FTP server.

Products tested : GNV, ACC, SCA, KBR, LRI instruments for GRACE-FO/GRACE
Server          : gfz_ftp  (ftp://isdcftp.gfz-potsdam.de)
"""
from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from gnss_ppp_products.assets.center.config import GNSSCenterConfig
from gnss_ppp_products.assets.leo.query import LEOFileQuery
from gnss_ppp_products.assets.server.config import ServerProtocol
from gnss_ppp_products.server.products import process_product_query

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CONFIG_DIR = Path(__file__).resolve().parent.parent / "src" / "gnss_ppp_products" / "assets" / "config_files"
DATE_GRACE_FO = datetime.date(2024, 1, 15)


@pytest.fixture(scope="module")
def gfz_center() -> GNSSCenterConfig:
    return GNSSCenterConfig.from_yaml(CONFIG_DIR / "gfz.yaml")


@pytest.fixture(scope="module")
def leo_queries(gfz_center) -> list[LEOFileQuery]:
    return gfz_center.build_leo_queries(DATE_GRACE_FO)


# ---------------------------------------------------------------------------
# Unit: Config → Query expansion
# ---------------------------------------------------------------------------


class TestLEOQueryExpansion:
    """Verify that GFZ center config expands LEO queries correctly."""

    def test_queries_returned(self, leo_queries) -> None:
        assert len(leo_queries) > 0

    def test_query_types(self, leo_queries) -> None:
        for q in leo_queries:
            assert isinstance(q, LEOFileQuery)

    def test_server_attached(self, leo_queries) -> None:
        for q in leo_queries:
            assert q.server is not None
            assert q.server.id == "gfz_ftp"

    def test_server_protocol_is_ftp(self, leo_queries) -> None:
        for q in leo_queries:
            assert q.server.protocol == ServerProtocol.FTP

    def test_grace_fo_queries_exist(self, leo_queries) -> None:
        gracefo = [q for q in leo_queries if "grace-fo" in q.directory]
        assert len(gracefo) > 0

    def test_instrument_coverage(self, leo_queries) -> None:
        """Multiple instruments should appear across queries."""
        instruments = set()
        for q in leo_queries:
            for instr in ("GNV1B", "ACC1B", "SCA1B", "KBR1B", "LRI1B"):
                if instr in q.filename:
                    instruments.add(instr)
        assert len(instruments) >= 3, f"Expected >=3 instruments, got {instruments}"

    def test_directories_contain_year(self, leo_queries) -> None:
        for q in leo_queries:
            assert "2024" in q.directory


# ---------------------------------------------------------------------------
# Integration: Probe GFZ FTP server
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestLEOFTPProbe:
    """Probe GFZ FTP to find GRACE-FO Level-1B files."""

    @pytest.fixture(scope="class")
    def probe_results(self, leo_queries) -> list[LEOFileQuery]:
        target = next(
            (q for q in leo_queries if "GNV1B" in q.filename and "grace-fo" in q.directory),
            None,
        )
        assert target is not None, "No GRACE-FO GNV query found"
        return process_product_query(target)

    def test_found_files(self, probe_results) -> None:
        assert len(probe_results) > 0, "No files found on GFZ FTP server"

    def test_filename_contains_gnv(self, probe_results) -> None:
        for result in probe_results:
            assert "GNV1B" in result.filename

    def test_server_preserved(self, probe_results) -> None:
        for result in probe_results:
            assert result.server is not None
            assert result.server.protocol == ServerProtocol.FTP
