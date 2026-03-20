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
LOCAL_CONFIG = _CONFIGS_DIR / "local" / "local_config.yaml"
CENTERS_DIR = _CONFIGS_DIR / "centers"


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
        local_config=str(LOCAL_CONFIG),
        remote_specs=list(center_dicts),
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
    return _load_center_yaml("cddis_config_v2.yaml")


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
def multi_env(wuhan_config, cod_config, cddis_config) -> ProductEnvironment:
    """Environment with all three centers registered."""
    return _build_env(wuhan_config, cod_config, cddis_config)


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
def fetcher() -> ResourceFetcher:
    return ResourceFetcher(ftp_timeout=30)


@pytest.fixture(scope="session")
def test_date() -> datetime.datetime:
    return TEST_DATE
