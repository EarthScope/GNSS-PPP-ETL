"""Tests for GNSSNetworkRegistry loading and source_product resolution."""

from __future__ import annotations

import pytest
from gnss_product_management.defaults import DefaultProductEnvironment
from gnss_product_management.environments.gnss_station_network import GNSSNetworkRegistry

# ── Paths ──────────────────────────────────────────────────────────────
from gpm_specs.configs import NETWORKS_RESOURCE_DIR

# ── GNSSNetworkRegistry loading ───────────────────────────────────────


class TestGNSSNetworkRegistryLoading:
    @pytest.fixture(scope="class")
    def registry(self) -> GNSSNetworkRegistry:
        return GNSSNetworkRegistry.from_config(NETWORKS_RESOURCE_DIR)

    def test_ert_loaded(self, registry) -> None:
        assert "ERT" in registry.network_ids

    def test_config_fields(self, registry) -> None:
        config = registry.config_for("ERT")
        assert config.id == "ERT"
        assert len(config.servers) > 0

    def test_unknown_network_raises(self, registry) -> None:
        with pytest.raises(KeyError, match="UNKNOWN"):
            registry.config_for("UNKNOWN")

    def test_non_network_yaml_skipped(self, tmp_path) -> None:
        (tmp_path / "not_a_network.yaml").write_text("some_key: value\n")
        reg = GNSSNetworkRegistry.from_config(tmp_path)
        assert reg.network_ids == []

    def test_resource_ids_matches_network_ids(self, registry) -> None:
        assert registry.resource_ids == registry.network_ids


# ── source_product ────────────────────────────────────────────────────


class TestSourceProduct:
    @pytest.fixture(scope="class")
    def registry(self) -> GNSSNetworkRegistry:
        reg = GNSSNetworkRegistry.from_config(NETWORKS_RESOURCE_DIR)
        reg.bind(DefaultProductEnvironment)
        return reg

    def test_resolves_rinex_obs_v3(self, registry) -> None:
        from gnss_product_management.specifications.parameters.parameter import Parameter
        from gnss_product_management.specifications.products.product import Product

        product = Product(
            name="RINEX_OBS",
            parameters=[Parameter(name="V", value="3")],
        )
        targets = registry.source_product(product, "ERT")
        assert len(targets) >= 1
        assert all(t.server is not None for t in targets)

    def test_unknown_product_raises(self, registry) -> None:
        from gnss_product_management.specifications.products.product import Product

        product = Product(name="NONEXISTENT", parameters=[])
        with pytest.raises(KeyError, match="NONEXISTENT"):
            registry.source_product(product, "ERT")

    def test_unknown_resource_raises(self, registry) -> None:
        from gnss_product_management.specifications.products.product import Product

        product = Product(name="RINEX_OBS", parameters=[])
        with pytest.raises(KeyError, match="NOPE"):
            registry.source_product(product, "NOPE")
