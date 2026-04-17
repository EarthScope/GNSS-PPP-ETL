"""Tests for Phase 3: RINEX file search via SearchPlanner.search_stations() and StationQuery.search()."""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock, patch

import pytest
from gnss_product_management.client.station_query import StationQuery
from gnss_product_management.defaults import DefaultProductEnvironment
from gnss_product_management.environments.gnss_station_network import (
    GNSSNetworkRegistry,
    GNSSStation,
)
from gnss_product_management.factories.search_planner import SearchPlanner
from gpm_specs.configs import NETWORKS_RESOURCE_DIR

DATE = datetime.datetime(2025, 1, 15, tzinfo=datetime.timezone.utc)
# Day 15 of 2025, formatted:
EXPECTED_DDD = "015"
EXPECTED_YY = "25"
EXPECTED_YYYY = "2025"


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def ert_env() -> GNSSNetworkRegistry:
    reg = GNSSNetworkRegistry.from_config(NETWORKS_RESOURCE_DIR)
    reg.bind(DefaultProductEnvironment)
    return reg


@pytest.fixture(scope="module")
def planner() -> SearchPlanner:
    return SearchPlanner(
        product_registry=DefaultProductEnvironment,
        gnss_network_registry=GNSSNetworkRegistry.from_config(NETWORKS_RESOURCE_DIR),
        workspace=MagicMock(),
    )


@pytest.fixture
def two_stations() -> list[GNSSStation]:
    return [
        GNSSStation(site_code="FAIR", lat=64.978, lon=-147.499),
        GNSSStation(site_code="WHIT", lat=60.751, lon=-135.224),
    ]


@pytest.fixture
def one_station() -> list[GNSSStation]:
    return [GNSSStation(site_code="FAIR", lat=64.978, lon=-147.499)]


# ── search_stations() ─────────────────────────────────────────────────────────


class TestSearchStations:
    def test_returns_one_target_per_station_v3(self, planner, two_stations, ert_env) -> None:
        targets = planner.search_stations(
            stations=two_stations,
            date=DATE,
            version="3",
            network_env=ert_env,
            center_ids=["ERT"],
        )
        assert len(targets) == 2

    def test_returns_one_target_per_station_v2(self, planner, two_stations, ert_env) -> None:
        targets = planner.search_stations(
            stations=two_stations,
            date=DATE,
            version="2",
            network_env=ert_env,
            center_ids=["ERT"],
        )
        assert len(targets) == 2

    def test_v2_directory_has_date(self, planner, one_station, ert_env) -> None:
        targets = planner.search_stations(
            stations=one_station,
            date=DATE,
            version="2",
            network_env=ert_env,
            center_ids=["ERT"],
        )
        assert len(targets) == 1
        dir_val = targets[0].directory.value or targets[0].directory.pattern
        assert EXPECTED_YYYY in dir_val
        assert EXPECTED_DDD in dir_val
        # v2 path: archive/gnss/rinex/obs/{YYYY}/{DDD}/
        assert "rinex/obs" in dir_val

    def test_v3_directory_has_date(self, planner, one_station, ert_env) -> None:
        targets = planner.search_stations(
            stations=one_station,
            date=DATE,
            version="3",
            network_env=ert_env,
            center_ids=["ERT"],
        )
        assert len(targets) == 1
        dir_val = targets[0].directory.value or targets[0].directory.pattern
        assert EXPECTED_YYYY in dir_val
        assert EXPECTED_DDD in dir_val
        # v3 path: archive/gnss/rinex3/obs/{YYYY}/{DDD}/
        assert "rinex3/obs" in dir_val

    def test_v2_filename_pattern_includes_station_and_ddd(
        self, planner, one_station, ert_env
    ) -> None:
        targets = planner.search_stations(
            stations=one_station,
            date=DATE,
            version="2",
            network_env=ert_env,
            center_ids=["ERT"],
        )
        pattern = targets[0].product.filename.pattern
        # lowercase station code and DDD in v2 filename
        assert "fair" in pattern.lower()
        assert EXPECTED_DDD in pattern

    def test_v3_filename_pattern_includes_uppercase_station(
        self, planner, one_station, ert_env
    ) -> None:
        targets = planner.search_stations(
            stations=one_station,
            date=DATE,
            version="3",
            network_env=ert_env,
            center_ids=["ERT"],
        )
        pattern = targets[0].product.filename.pattern
        assert "FAIR" in pattern
        assert "rnx" in pattern

    def test_ssss_parameter_set_on_target(self, planner, one_station, ert_env) -> None:
        targets = planner.search_stations(
            stations=one_station,
            date=DATE,
            version="3",
            network_env=ert_env,
            center_ids=["ERT"],
        )
        params = {p.name: p.value for p in targets[0].product.parameters}
        assert params.get("SSSS") == "FAIR"
        assert params.get("V") == "3"

    def test_server_hostname_is_earthscope_archive(self, planner, one_station, ert_env) -> None:
        targets = planner.search_stations(
            stations=one_station,
            date=DATE,
            version="3",
            network_env=ert_env,
            center_ids=["ERT"],
        )
        assert "data.earthscope.org" in targets[0].server.hostname

    def test_unknown_center_skipped(self, planner, one_station, ert_env) -> None:
        targets = planner.search_stations(
            stations=one_station,
            date=DATE,
            version="3",
            network_env=ert_env,
            center_ids=["UNKNOWN"],
        )
        assert targets == []


# ── @registry.filesystem("ERT") ───────────────────────────────────────────────


class TestFilesystemFactory:
    def test_factory_registered(self, ert_env) -> None:
        factory = ert_env.registry.get_filesystem_factory("ERT")
        assert factory is not None

    def test_factory_callable_without_token(self, ert_env) -> None:
        factory = ert_env.registry.get_filesystem_factory("ERT")
        fs = factory({})
        assert fs is not None

    def test_factory_callable_with_token(self, ert_env) -> None:
        factory = ert_env.registry.get_filesystem_factory("ERT")
        fs = factory({"earthscope_token": "dummy_token_abc"})
        assert fs is not None


# ── StationQuery.search() ─────────────────────────────────────────────────────


class TestStationQuerySearch:
    def test_search_requires_on_date(self, ert_env) -> None:
        sq = StationQuery(
            wormhole=MagicMock(),
            search_planner=MagicMock(),
            network_env=ert_env,
        )
        with pytest.raises(ValueError, match="on"):
            sq.within(62.0, -140.0, 500.0).networks("ERT").search()

    def test_search_no_stations_returns_empty(self, ert_env, planner) -> None:
        """metadata() returning [] short-circuits to empty search."""
        wormhole = MagicMock()
        sq = StationQuery(
            wormhole=wormhole,
            search_planner=planner,
            network_env=ert_env,
        )
        with patch.object(sq.__class__, "metadata", return_value=[]):
            result = sq.within(62.0, -140.0, 500.0).networks("ERT").on(DATE).search()
        assert result == []
        wormhole.search.assert_not_called()

    def test_search_returns_found_resources(self, ert_env, planner) -> None:
        """End-to-end: mock metadata + mock wormhole listing."""
        from unittest.mock import MagicMock, patch

        from gnss_product_management.specifications.parameters.parameter import Parameter
        from gnss_product_management.specifications.products.product import PathTemplate, Product
        from gnss_product_management.specifications.remote.resource import SearchTarget, Server

        stations = [GNSSStation(site_code="FAIR", lat=64.978, lon=-147.499)]

        # Build a fake matched SearchTarget (what WormHole.search() returns)
        fake_server = Server(id="s", hostname="https://data.earthscope.org", protocol="https")
        fake_product = Product(
            name="RINEX_OBS",
            parameters=[
                Parameter(name="SSSS", value="FAIR"),
                Parameter(name="V", value="3"),
            ],
            filename=PathTemplate(
                pattern="FAIR.*\\.rnx",
                value="FAIR00USA_R_20250150000_01D_30S_MO.rnx.gz",
            ),
        )
        fake_target = SearchTarget(
            product=fake_product,
            server=fake_server,
            directory=PathTemplate(
                pattern="archive/gnss/rinex3/obs/2025/015/",
                value="archive/gnss/rinex3/obs/2025/015/",
            ),
        )

        wormhole = MagicMock()
        wormhole._connection_pool_factory = MagicMock()
        wormhole.search.return_value = [fake_target]

        sq = StationQuery(
            wormhole=wormhole,
            search_planner=planner,
            network_env=ert_env,
        )
        with patch.object(sq.__class__, "metadata", return_value=stations):
            results = sq.within(62.0, -140.0, 500.0).networks("ERT").on(DATE).search()

        assert len(results) == 1
        assert results[0].product == "RINEX_OBS"
        assert results[0].parameters.get("SSSS") == "FAIR"
        assert results[0].parameters.get("V") == "3"
        assert "FAIR00USA_R_20250150000_01D_30S_MO.rnx.gz" in results[0].uri

    def test_search_results_sorted_station_asc_version_desc(self, ert_env, planner) -> None:
        """Results sorted: station code ascending, RINEX version descending."""
        from gnss_product_management.specifications.parameters.parameter import Parameter
        from gnss_product_management.specifications.products.product import PathTemplate, Product
        from gnss_product_management.specifications.remote.resource import SearchTarget, Server

        def _make_target(code: str, version: str, filename: str) -> SearchTarget:
            return SearchTarget(
                product=Product(
                    name="RINEX_OBS",
                    parameters=[
                        Parameter(name="SSSS", value=code),
                        Parameter(name="V", value=version),
                    ],
                    filename=PathTemplate(pattern=".*", value=filename),
                ),
                server=Server(id="s", hostname="https://data.earthscope.org", protocol="https"),
                directory=PathTemplate(
                    pattern="archive/",
                    value="archive/gnss/rinex3/obs/2025/015/",
                ),
            )

        fake_targets = [
            _make_target("WHIT", "2", "whit0150.25o.Z"),
            _make_target("FAIR", "3", "FAIR00USA.rnx.gz"),
            _make_target("FAIR", "2", "fair0150.25o.Z"),
            _make_target("WHIT", "3", "WHIT00USA.rnx.gz"),
        ]

        wormhole = MagicMock()
        wormhole._connection_pool_factory = MagicMock()
        wormhole.search.return_value = fake_targets

        stations = [
            GNSSStation(site_code="FAIR", lat=64.978, lon=-147.499),
            GNSSStation(site_code="WHIT", lat=60.751, lon=-135.224),
        ]

        sq = StationQuery(
            wormhole=wormhole,
            search_planner=planner,
            network_env=ert_env,
        )
        with patch.object(sq.__class__, "metadata", return_value=stations):
            results = sq.within(62.0, -140.0, 500.0).networks("ERT").on(DATE).search()

        codes_and_versions = [(r.parameters["SSSS"], r.parameters["V"]) for r in results]
        # Expected: FAIR v3, FAIR v2, WHIT v3, WHIT v2
        assert codes_and_versions == [("FAIR", "3"), ("FAIR", "2"), ("WHIT", "3"), ("WHIT", "2")]

    def test_multi_center_results_both_retained(self, planner) -> None:
        """Multi-center results for same station are both in output."""
        from gnss_product_management.specifications.parameters.parameter import Parameter
        from gnss_product_management.specifications.products.product import PathTemplate, Product
        from gnss_product_management.specifications.remote.resource import (
            ResourceProductSpec,
            ResourceSpec,
            SearchTarget,
            Server,
        )

        # Build a two-center environment
        reg = GNSSNetworkRegistry.from_config(NETWORKS_RESOURCE_DIR)
        reg.bind(DefaultProductEnvironment)
        # Clone ERT as a second center (simulate)
        reg._configs["ERT2"] = ResourceSpec(
            id="ERT2",
            name="ERT Mirror",
            servers=[Server(id="s2", hostname="https://mirror.example.com", protocol="https")],
            products=[
                ResourceProductSpec(
                    id="ert2_rinex3",
                    product_name="RINEX_OBS",
                    server_id="s2",
                    parameters=[Parameter(name="V", value="3")],
                    directory=PathTemplate(pattern="obs/{YYYY}/{DDD}/"),
                )
            ],
        )
        two_center_env = reg

        def _make_target(hostname: str) -> SearchTarget:
            return SearchTarget(
                product=Product(
                    name="RINEX_OBS",
                    parameters=[
                        Parameter(name="SSSS", value="FAIR"),
                        Parameter(name="V", value="3"),
                    ],
                    filename=PathTemplate(pattern=".*", value="FAIR00USA.rnx.gz"),
                ),
                server=Server(id="s", hostname=hostname, protocol="https"),
                directory=PathTemplate(pattern="obs/", value="obs/2025/015/"),
            )

        wormhole = MagicMock()
        wormhole._connection_pool_factory = MagicMock()
        wormhole.search.return_value = [
            _make_target("https://data.earthscope.org"),
            _make_target("https://mirror.example.com"),
        ]

        stations = [GNSSStation(site_code="FAIR", lat=64.978, lon=-147.499)]
        sq = StationQuery(
            wormhole=wormhole,
            search_planner=planner,
            network_env=two_center_env,
        )
        with patch.object(sq.__class__, "metadata", return_value=stations):
            results = sq.within(62.0, -140.0, 500.0).networks("ERT", "ERT2").on(DATE).search()

        # Both centers retained
        assert len(results) == 2
        hostnames = {r.hostname for r in results}
        assert "data.earthscope.org" in hostnames
        assert "mirror.example.com" in hostnames
