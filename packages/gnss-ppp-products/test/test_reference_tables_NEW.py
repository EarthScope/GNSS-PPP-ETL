"""
Tests: Reference table products via GNSSCenterConfig (Wuhan).

Load the Wuhan center config—FTP server—and verify that
ReferenceTableFileQuery objects build correctly.  Integration tests
probe the Wuhan FTP server to find actual reference table files.

Products tested : leap_seconds, sat_parameters
Server          : wuhan_ftp  (ftp://igs.gnsswhu.cn)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from gnss_ppp_products.assets.center.config import GNSSCenterConfig
from gnss_ppp_products.assets.reference_tables.query import ReferenceTableFileQuery
from gnss_ppp_products.assets.reference_tables.base import ReferenceTableType
from gnss_ppp_products.assets.server.config import ServerProtocol
from gnss_ppp_products.server.products import process_product_query

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CONFIG_DIR = Path(__file__).resolve().parent.parent / "src" / "gnss_ppp_products" / "assets" / "config_files"


@pytest.fixture(scope="module")
def wuhan_center() -> GNSSCenterConfig:
    return GNSSCenterConfig.from_yaml(CONFIG_DIR / "wuhan.yaml")


@pytest.fixture(scope="module")
def reference_table_queries(wuhan_center) -> list[ReferenceTableFileQuery]:
    return wuhan_center.build_reference_table_queries()


# ---------------------------------------------------------------------------
# Unit: Config → Query expansion
# ---------------------------------------------------------------------------


class TestReferenceTableQueryExpansion:
    """Verify that Wuhan center config expands reference table queries."""

    def test_queries_returned(self, reference_table_queries) -> None:
        assert len(reference_table_queries) > 0

    def test_query_types(self, reference_table_queries) -> None:
        for q in reference_table_queries:
            assert isinstance(q, ReferenceTableFileQuery)

    def test_server_attached(self, reference_table_queries) -> None:
        for q in reference_table_queries:
            assert q.server is not None
            assert q.server.id == "wuhan_ftp"

    def test_server_protocol_is_ftp(self, reference_table_queries) -> None:
        for q in reference_table_queries:
            assert q.server.protocol == ServerProtocol.FTP

    def test_leap_seconds_present(self, reference_table_queries) -> None:
        leap = [q for q in reference_table_queries if q.filename == "leap.sec"]
        assert len(leap) == 1

    def test_sat_parameters_present(self, reference_table_queries) -> None:
        sat = [q for q in reference_table_queries if q.filename == "sat_parameters"]
        assert len(sat) == 1

    def test_directory(self, reference_table_queries) -> None:
        for q in reference_table_queries:
            assert q.directory == "pub/whu/phasebias/table"


# ---------------------------------------------------------------------------
# Integration: Probe Wuhan FTP server
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestReferenceTableFTPProbe:
    """Probe Wuhan FTP to find reference table files."""

    @pytest.fixture(scope="class")
    def leap_probe(self, reference_table_queries) -> list[ReferenceTableFileQuery]:
        target = next((q for q in reference_table_queries if q.filename == "leap.sec"), None)
        assert target is not None
        return process_product_query(target)

    @pytest.fixture(scope="class")
    def sat_probe(self, reference_table_queries) -> list[ReferenceTableFileQuery]:
        target = next((q for q in reference_table_queries if q.filename == "sat_parameters"), None)
        assert target is not None
        return process_product_query(target)

    def test_leap_seconds_found(self, leap_probe) -> None:
        assert len(leap_probe) > 0, "leap.sec not found on Wuhan FTP"

    def test_sat_parameters_found(self, sat_probe) -> None:
        assert len(sat_probe) > 0, "sat_parameters not found on Wuhan FTP"

    def test_server_preserved(self, leap_probe) -> None:
        for result in leap_probe:
            assert result.server.protocol == ServerProtocol.FTP
