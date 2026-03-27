"""Shared test fixtures for the gnss-ppp-products test suite.

Builds a ProductEnvironment + QueryFactory from the YAML spec files under
configs/ and the center configs under configs/centers/.  These are reused
across all test modules so the heavy catalog-construction work happens once
per session.
"""
from __future__ import annotations

import datetime
from pathlib import Path

import pytest
import yaml

from gnss_ppp_products.factories import ProductEnvironment, QueryFactory, ResourceFetcher
from gnss_ppp_products.specifications.parameters.parameter import ParameterCatalog
from gnss_ppp_products.specifications.format.format_spec import FormatSpecCatalog
from gnss_ppp_products.specifications.products.catalog import ProductSpecCatalog

# ── Paths to YAML config files ────────────────────────────────────
_CONFIGS_DIR = (
    Path(__file__).resolve().parent.parent
    / "src" / "gnss_ppp_products" / "configs"
)
META_SPEC_YAML = _CONFIGS_DIR / "meta" / "meta_spec.yaml"
PRODUCT_SPEC_YAML = _CONFIGS_DIR / "products" / "product_spec.yaml"
LOCAL_CONFIGS = list((_CONFIGS_DIR / "local").glob("*.yaml"))
CENTERS_DIR = _CONFIGS_DIR / "centers"
DEP_SPECS = list((_CONFIGS_DIR / "dependencies").glob("*.yaml"))


# ── Load specs from YAML configs via specification layer ──────────
parameter_catalog = ParameterCatalog.from_yaml(META_SPEC_YAML)
format_spec_catalog = FormatSpecCatalog.from_yaml(PRODUCT_SPEC_YAML)
product_spec_catalog = ProductSpecCatalog.from_yaml(PRODUCT_SPEC_YAML)

# ── Reference date for all tests ──────────────────────────────────
TEST_DATE = datetime.datetime(2025, 1, 15, tzinfo=datetime.timezone.utc)


# ── Helpers ────────────────────────────────────────────────────────

def _load_center_yaml(filename: str) -> dict:
    """Load a single center YAML from the configs/centers/ directory."""
    path = CENTERS_DIR / filename
    with open(path) as f:
        return yaml.safe_load(f)


def _build_env(*center_dicts: dict) -> ProductEnvironment:
    """Build a ProductEnvironment wired to specific center configs."""
    return ProductEnvironment.from_yaml(
        base_dir="/tmp/gnss_test",
        meta_spec_yaml=META_SPEC_YAML,
        product_spec_yaml=PRODUCT_SPEC_YAML,
        local_configs=LOCAL_CONFIGS,
        remote_specs=list(center_dicts),
        dependency_specs=DEP_SPECS,
    )


# ── Session-scoped fixtures ───────────────────────────────────────

@pytest.fixture(scope="session")
def wuhan_config() -> dict:
    return _load_center_yaml("wuhan_config.yaml")


@pytest.fixture(scope="session")
def cod_config() -> dict:
    return _load_center_yaml("cod_config.yaml")


@pytest.fixture(scope="session")
def cddis_config() -> dict:
    return _load_center_yaml("cddis_config.yaml")


@pytest.fixture(scope="session")
def igs_config() -> dict:
    return _load_center_yaml("igs_config.yaml")


@pytest.fixture(scope="session")
def vmf_config() -> dict:
    return _load_center_yaml("vmf_config.yaml")


@pytest.fixture(scope="session")
def gfz_config() -> dict:
    return _load_center_yaml("gfz_config.yaml")


@pytest.fixture(scope="session")
def wuhan_env(wuhan_config) -> ProductEnvironment:
    return _build_env(wuhan_config)


@pytest.fixture(scope="session")
def cod_env(cod_config) -> ProductEnvironment:
    return _build_env(cod_config)


@pytest.fixture(scope="session")
def cddis_env(cddis_config) -> ProductEnvironment:
    return _build_env(cddis_config)


@pytest.fixture(scope="session")
def multi_env(wuhan_config, cod_config, cddis_config, igs_config, gfz_config, vmf_config) -> ProductEnvironment:
    """Environment with all centers registered."""
    return _build_env(wuhan_config, cod_config, cddis_config, igs_config, gfz_config, vmf_config)


@pytest.fixture(scope="session")
def igs_env(igs_config) -> ProductEnvironment:
    return _build_env(igs_config)


@pytest.fixture(scope="session")
def vmf_env(vmf_config) -> ProductEnvironment:
    return _build_env(vmf_config)


@pytest.fixture(scope="session")
def gfz_env(gfz_config) -> ProductEnvironment:
    return _build_env(gfz_config)


@pytest.fixture(scope="session")
def wuhan_qf(wuhan_env) -> QueryFactory:
    return QueryFactory(
        remote_factory=wuhan_env.remote_factory,
        local_factory=wuhan_env.local_factory,
        product_catalog=wuhan_env.product_catalog,
        parameter_catalog=wuhan_env.parameter_catalog,
    )


@pytest.fixture(scope="session")
def cod_qf(cod_env) -> QueryFactory:
    return QueryFactory(
        remote_factory=cod_env.remote_factory,
        local_factory=cod_env.local_factory,
        product_catalog=cod_env.product_catalog,
        parameter_catalog=cod_env.parameter_catalog,
    )


@pytest.fixture(scope="session")
def cddis_qf(cddis_env) -> QueryFactory:
    return QueryFactory(
        remote_factory=cddis_env.remote_factory,
        local_factory=cddis_env.local_factory,
        product_catalog=cddis_env.product_catalog,
        parameter_catalog=cddis_env.parameter_catalog,
    )


@pytest.fixture(scope="session")
def igs_qf(igs_env) -> QueryFactory:
    return QueryFactory(
        remote_factory=igs_env.remote_factory,
        local_factory=igs_env.local_factory,
        product_catalog=igs_env.product_catalog,
        parameter_catalog=igs_env.parameter_catalog,
    )


@pytest.fixture(scope="session")
def vmf_qf(vmf_env) -> QueryFactory:
    return QueryFactory(
        remote_factory=vmf_env.remote_factory,
        local_factory=vmf_env.local_factory,
        product_catalog=vmf_env.product_catalog,
        parameter_catalog=vmf_env.parameter_catalog,
    )


@pytest.fixture(scope="session")
def gfz_qf(gfz_env) -> QueryFactory:
    return QueryFactory(
        remote_factory=gfz_env.remote_factory,
        local_factory=gfz_env.local_factory,
        product_catalog=gfz_env.product_catalog,
        parameter_catalog=gfz_env.parameter_catalog,
    )


@pytest.fixture(scope="session")
def fetcher() -> ResourceFetcher:
    return ResourceFetcher()


@pytest.fixture(scope="session")
def test_date() -> datetime.datetime:
    return TEST_DATE
