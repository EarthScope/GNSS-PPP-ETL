"""Tests for Phase 4: StationQuery.download() with per-station fallback."""

from __future__ import annotations

import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from gnss_product_management.client.station_query import StationQuery
from gnss_product_management.defaults import DefaultProductEnvironment
from gnss_product_management.environments.gnss_station_network import GNSSNetworkRegistry
from gnss_product_management.factories.models import FoundResource
from gnss_product_management.factories.search_planner import SearchPlanner
from gpm_specs.configs import NETWORKS_RESOURCE_DIR

DATE = datetime.datetime(2025, 1, 15, tzinfo=datetime.timezone.utc)


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


def _make_fr(ssss: str, version: str, uri: str) -> FoundResource:
    """Helper to make a FoundResource with a fake _query."""
    fr = FoundResource(
        product="RINEX_OBS",
        source="remote",
        uri=uri,
        parameters={"SSSS": ssss, "V": version},
        date=DATE,
    )
    fr._query = MagicMock()  # Fake SearchTarget
    return fr


# ── download() return type and signature ─────────────────────────────────────


class TestDownloadReturnType:
    def test_returns_list_not_paths(self, ert_env, planner) -> None:
        """download() returns list[FoundResource], not list[Path]."""
        wormhole = MagicMock()
        wormhole._connection_pool_factory = MagicMock()
        fake_path = Path("/tmp/FAIR00USA.rnx")
        wormhole.download_one.return_value = fake_path

        candidates = [_make_fr("FAIR", "3", "https://example.com/FAIR.rnx.gz")]

        sq = StationQuery(wormhole=wormhole, search_planner=planner, network_env=ert_env)
        with patch.object(sq.__class__, "search", return_value=candidates):
            results = sq.within(62.0, -140.0, 500.0).networks("ERT").on(DATE).download("local")

        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], FoundResource)

    def test_local_path_set_on_winner(self, ert_env, planner) -> None:
        """local_path is populated on the winning FoundResource."""
        fake_path = Path("/tmp/FAIR00USA.rnx")
        wormhole = MagicMock()
        wormhole._connection_pool_factory = MagicMock()
        wormhole.download_one.return_value = fake_path

        candidates = [_make_fr("FAIR", "3", "https://example.com/FAIR.rnx.gz")]

        sq = StationQuery(wormhole=wormhole, search_planner=planner, network_env=ert_env)
        with patch.object(sq.__class__, "search", return_value=candidates):
            results = sq.within(62.0, -140.0, 500.0).networks("ERT").on(DATE).download("local")

        assert results[0].local_path == fake_path

    def test_empty_search_returns_empty(self, ert_env, planner) -> None:
        wormhole = MagicMock()
        sq = StationQuery(wormhole=wormhole, search_planner=planner, network_env=ert_env)
        with patch.object(sq.__class__, "search", return_value=[]):
            results = sq.within(62.0, -140.0, 500.0).networks("ERT").on(DATE).download("local")
        assert results == []


# ── Per-station fallback ──────────────────────────────────────────────────────


class TestPerStationFallback:
    def test_first_center_success_stops_trying(self, ert_env, planner) -> None:
        """If the first center succeeds, the second is never tried."""
        primary_path = Path("/tmp/FAIR_primary.rnx")
        wormhole = MagicMock()
        wormhole._connection_pool_factory = MagicMock()
        wormhole.download_one.return_value = primary_path

        candidates = [
            _make_fr("FAIR", "3", "https://primary.example.com/FAIR.rnx.gz"),
            _make_fr("FAIR", "3", "https://mirror.example.com/FAIR.rnx.gz"),
        ]

        sq = StationQuery(wormhole=wormhole, search_planner=planner, network_env=ert_env)
        with patch.object(sq.__class__, "search", return_value=candidates):
            results = sq.within(62.0, -140.0, 500.0).networks("ERT").on(DATE).download("local")

        assert len(results) == 1
        assert results[0].local_path == primary_path
        # download_one called exactly once (first center succeeded)
        wormhole.download_one.assert_called_once()

    def test_fallback_to_second_center_on_failure(self, ert_env, planner) -> None:
        """If the first center fails, the second is tried automatically."""
        fallback_path = Path("/tmp/FAIR_fallback.rnx")
        wormhole = MagicMock()
        wormhole._connection_pool_factory = MagicMock()
        # First call fails, second succeeds
        wormhole.download_one.side_effect = [None, fallback_path]

        candidates = [
            _make_fr("FAIR", "3", "https://primary.example.com/FAIR.rnx.gz"),
            _make_fr("FAIR", "3", "https://mirror.example.com/FAIR.rnx.gz"),
        ]

        sq = StationQuery(wormhole=wormhole, search_planner=planner, network_env=ert_env)
        with patch.object(sq.__class__, "search", return_value=candidates):
            results = sq.within(62.0, -140.0, 500.0).networks("ERT").on(DATE).download("local")

        assert len(results) == 1
        assert results[0].local_path == fallback_path
        assert wormhole.download_one.call_count == 2

    def test_all_centers_fail_station_absent(self, ert_env, planner) -> None:
        """If all centers fail for a station, it's absent from results (no exception)."""
        wormhole = MagicMock()
        wormhole._connection_pool_factory = MagicMock()
        wormhole.download_one.return_value = None

        candidates = [
            _make_fr("FAIR", "3", "https://primary.example.com/FAIR.rnx.gz"),
            _make_fr("FAIR", "3", "https://mirror.example.com/FAIR.rnx.gz"),
        ]

        sq = StationQuery(wormhole=wormhole, search_planner=planner, network_env=ert_env)
        with patch.object(sq.__class__, "search", return_value=candidates):
            results = sq.within(62.0, -140.0, 500.0).networks("ERT").on(DATE).download("local")

        assert results == []

    def test_exception_during_download_triggers_fallback(self, ert_env, planner) -> None:
        """Exceptions during download_one are caught and fallback is tried."""
        fallback_path = Path("/tmp/FAIR_fallback.rnx")
        wormhole = MagicMock()
        wormhole._connection_pool_factory = MagicMock()
        wormhole.download_one.side_effect = [
            Exception("connection error"),
            fallback_path,
        ]

        candidates = [
            _make_fr("FAIR", "3", "https://primary.example.com/FAIR.rnx.gz"),
            _make_fr("FAIR", "3", "https://mirror.example.com/FAIR.rnx.gz"),
        ]

        sq = StationQuery(wormhole=wormhole, search_planner=planner, network_env=ert_env)
        with patch.object(sq.__class__, "search", return_value=candidates):
            results = sq.within(62.0, -140.0, 500.0).networks("ERT").on(DATE).download("local")

        assert len(results) == 1
        assert results[0].local_path == fallback_path

    def test_multi_station_one_winner_each(self, ert_env, planner) -> None:
        """Each station gets exactly one winner in the result list."""
        path_fair = Path("/tmp/FAIR.rnx")
        path_whit = Path("/tmp/WHIT.rnx")
        wormhole = MagicMock()
        wormhole._connection_pool_factory = MagicMock()
        wormhole.download_one.side_effect = [path_fair, path_whit]

        candidates = [
            _make_fr("FAIR", "3", "https://example.com/FAIR.rnx.gz"),
            _make_fr("WHIT", "3", "https://example.com/WHIT.rnx.gz"),
        ]

        sq = StationQuery(wormhole=wormhole, search_planner=planner, network_env=ert_env)
        with patch.object(sq.__class__, "search", return_value=candidates):
            results = sq.within(62.0, -140.0, 500.0).networks("ERT").on(DATE).download("local")

        assert len(results) == 2
        codes = {r.parameters["SSSS"] for r in results}
        assert codes == {"FAIR", "WHIT"}
