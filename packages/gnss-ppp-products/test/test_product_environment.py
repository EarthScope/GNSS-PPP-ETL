"""Tests for ProductEnvironment — Phase 1: construction, classify, properties."""

import os
import tempfile
from pathlib import Path

import pytest

from gnss_ppp_products.factories import ProductEnvironment
from gnss_ppp_products.configs import (
    META_SPEC_YAML,
    PRODUCT_SPEC_YAML,
    LOCAL_SPEC_DIR,
    CENTERS_RESOURCE_DIR,
    DEPENDENCY_SPEC_DIR,
)


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def workspace_dir():
    """Create a real temporary directory for workspace testing."""
    with tempfile.TemporaryDirectory(prefix="gnss_test_") as d:
        yield d


@pytest.fixture(scope="module")
def env(workspace_dir):
    """A full ProductEnvironment built via workspace=..."""
    return ProductEnvironment(workspace=workspace_dir)


@pytest.fixture(scope="module")
def env_with_alias(workspace_dir):
    """ProductEnvironment with explicit alias."""
    return ProductEnvironment(workspace=(workspace_dir, "campaign1"))


# ── Construction ──────────────────────────────────────────────────


class TestWorkspaceConstruction:
    """Environment built via workspace=... auto-loads everything."""

    def test_base_dir(self, env, workspace_dir):
        assert env.base_dir == Path(workspace_dir)

    def test_alias_defaults_to_stem(self, env, workspace_dir):
        assert env.alias == Path(workspace_dir).stem

    def test_alias_override(self, env_with_alias):
        assert env_with_alias.alias == "campaign1"

    def test_has_products(self, env):
        assert len(env.product_catalog.products) > 0

    def test_has_remote_centers(self, env):
        assert len(env.remote_factory.centers) > 0

    def test_has_local_factory(self, env):
        assert env.local_factory is not None

    def test_has_dependency_specs(self, env):
        assert len(env.dependency_specs) > 0

    def test_has_parameter_catalog(self, env):
        assert len(env.parameter_catalog.parameters) > 0

    def test_has_format_catalog(self, env):
        assert env.format_catalog is not None


class TestWorkspaceValidation:
    """base_dir validation at construction time."""

    def test_nonexistent_workspace_raises(self):
        with pytest.raises(FileNotFoundError, match="does not exist"):
            ProductEnvironment(workspace="/nonexistent/path/xyz")

    def test_no_args_raises(self):
        with pytest.raises(TypeError, match="workspace.*base_dir"):
            ProductEnvironment()


class TestRepr:
    """ProductEnvironment __repr__ includes alias."""

    def test_repr_contains_alias(self, env):
        r = repr(env)
        assert "alias=" in r
        assert env.alias in r


# ── Immutability ──────────────────────────────────────────────────


class TestImmutability:
    """No mutation methods exposed on the public API."""

    def test_no_register_remote(self, env):
        assert not hasattr(env, "register_remote")

    def test_no_register_dependency_spec(self, env):
        assert not hasattr(env, "register_dependency_spec")

    def test_local_factory_not_settable(self, env):
        with pytest.raises(AttributeError):
            env.local_factory = "/some/path"


# ── Classify ──────────────────────────────────────────────────────


class TestClassify:
    """classify() parses filenames into product metadata dicts."""

    @pytest.mark.parametrize(
        "filename, expected_product, expected_params",
        [
            (
                "WUM0MGXFIN_20240010000_01D_05M_ORB.SP3.gz",
                "ORBIT",
                {"AAA": "WUM", "TTT": "FIN", "CNT": "ORB", "FMT": "SP3", "YYYY": "2024"},
            ),
            (
                "COD0OPSRAP_20251000000_01D_30S_CLK.CLK.gz",
                "CLOCK",
                {"AAA": "COD", "TTT": "RAP", "CNT": "CLK", "FMT": "CLK"},
            ),
            (
                "GFZ0MGXRAP_20251000000_01D_01D_ERP.ERP.gz",
                "ERP",
                {"AAA": "GFZ", "TTT": "RAP", "CNT": "ERP", "FMT": "ERP"},
            ),
            (
                "WUM0MGXFIN_20240010000_01D_01D_OSB.BIA.gz",
                "BIA",
                {"AAA": "WUM", "TTT": "FIN", "CNT": "OSB", "FMT": "BIA"},
            ),
            ("igs20.atx", "ATTATX", {"REFFRAME": "igs20"}),
            (
                "NCC12500.25o", "RINEX_OBS", {"SSSS": "NCC1", "DDD": "250", "YY": "25", "T": "o"}
            ),
        ],
    )
    def test_classify_product(self, env, filename, expected_product, expected_params):
        result = env.classify(filename)
        assert result is not None
        assert result["product"] == expected_product
        for key, val in expected_params.items():
            assert result["parameters"][key] == val

    def test_classify_returns_dict_shape(self, env):
        result = env.classify("WUM0MGXFIN_20240010000_01D_05M_ORB.SP3.gz")
        assert isinstance(result, dict)
        assert "product" in result
        assert "format" in result
        assert "version" in result
        assert "variant" in result
        assert "parameters" in result
        assert result["format"] == "PRODUCT"
        assert result["version"] == "1"
        assert result["variant"] == "default"

    def test_classify_returns_parameters(self, env):
        result = env.classify("WUM0MGXFIN_20240010000_01D_05M_ORB.SP3.gz")
        assert result["parameters"]["AAA"] == "WUM"
        assert result["parameters"]["YYYY"] == "2024"

    def test_classify_unknown_returns_none(self, env):
        result = env.classify("totally_unknown_file.xyz")
        assert result is None

    def test_classify_uncompressed(self, env):
        result = env.classify("IGS0OPSRAP_20251000000_01D_15M_ORB.SP3")
        assert result is not None
        assert result["product"] == "ORBIT"
        assert result["parameters"]["AAA"] == "IGS"

    def test_classify_strips_path(self, env):
        result = env.classify("/data/products/WUM/WUM0MGXFIN_20240010000_01D_05M_ORB.SP3.gz")
        assert result is not None
        assert result["product"] == "ORBIT"
        assert result["parameters"]["AAA"] == "WUM"

    def test_classify_with_constraint_parameters(self, env):
        from gnss_ppp_products.specifications.parameters.parameter import Parameter

        params = [Parameter(name="CNT", value="ORB")]
        result = env.classify(
            "WUM0MGXFIN_20240010000_01D_05M_ORB.SP3.gz", parameters=params
        )
        assert result is not None
        assert result["product"] == "ORBIT"

    def test_classify_conflicting_parameters_returns_none(self, env):
        from gnss_ppp_products.specifications.parameters.parameter import Parameter

        params = [Parameter(name="CNT", value="CLK")]
        result = env.classify(
            "WUM0MGXFIN_20240010000_01D_05M_ORB.SP3.gz", parameters=params
        )
        assert result is None
