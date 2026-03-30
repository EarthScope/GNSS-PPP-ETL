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

from gnss_ppp_products.factories import (
    ProductEnvironment,
    WorkSpace,
    QueryFactory,
    ResourceFetcher,
)
from gnss_ppp_products.specifications.parameters.parameter import ParameterCatalog
from gnss_ppp_products.specifications.format.format_spec import FormatSpecCatalog
from gnss_ppp_products.specifications.products.catalog import ProductSpecCatalog

# ── Paths to YAML config files ────────────────────────────────────
from gnss_management_specs.configs import (
    META_SPEC_YAML,
    FORMAT_SPEC_YAML,
    PRODUCT_SPEC_YAML,
    LOCAL_SPEC_DIR,
    CENTERS_RESOURCE_DIR,
)

LOCAL_CONFIGS = list(Path(LOCAL_SPEC_DIR).glob("*.yaml"))
CENTERS_DIR = CENTERS_RESOURCE_DIR


# ── Load specs from YAML configs via specification layer ──────────
parameter_catalog = ParameterCatalog.from_yaml(META_SPEC_YAML)
format_spec_catalog = FormatSpecCatalog.from_yaml(FORMAT_SPEC_YAML)
product_spec_catalog = ProductSpecCatalog.from_yaml(PRODUCT_SPEC_YAML)

# ── Reference date for all tests ──────────────────────────────────
TEST_DATE = datetime.datetime(2025, 1, 15, tzinfo=datetime.timezone.utc)


# ── Helpers ────────────────────────────────────────────────────────


def _build_env(*center_yamls: str) -> ProductEnvironment:
    """Build a ProductEnvironment wired to specific center config files."""
    env = ProductEnvironment()
    env.add_parameter_spec(META_SPEC_YAML)
    env.add_format_spec(FORMAT_SPEC_YAML)
    env.add_product_spec(PRODUCT_SPEC_YAML)
    for name in center_yamls:
        env.add_resource_spec(CENTERS_DIR / name)
    env.build()
    return env


def _build_workspace(base_dir: Path) -> WorkSpace:
    """Build a WorkSpace with all local resource specs registered to *base_dir*."""
    ws = WorkSpace()
    for path in LOCAL_CONFIGS:
        ws.add_resource_spec(path)
    ws.register_spec(base_dir=base_dir, spec_ids=["local_config"])
    return ws


# ── Session-scoped fixtures ───────────────────────────────────────


@pytest.fixture(scope="session")
def workspace(tmp_path_factory) -> WorkSpace:
    base = tmp_path_factory.mktemp("gnss_workspace")
    return _build_workspace(base)


@pytest.fixture(scope="session")
def wuhan_env() -> ProductEnvironment:
    return _build_env("wuhan_config.yaml")


@pytest.fixture(scope="session")
def cod_env() -> ProductEnvironment:
    return _build_env("cod_config.yaml")


@pytest.fixture(scope="session")
def cddis_env() -> ProductEnvironment:
    return _build_env("cddis_config.yaml")


@pytest.fixture(scope="session")
def multi_env() -> ProductEnvironment:
    """Environment with all centers registered."""
    return _build_env(
        "wuhan_config.yaml",
        "cod_config.yaml",
        "cddis_config.yaml",
        "igs_config.yaml",
        "gfz_config.yaml",
        "vmf_config.yaml",
    )


@pytest.fixture(scope="session")
def igs_env() -> ProductEnvironment:
    return _build_env("igs_config.yaml")


@pytest.fixture(scope="session")
def vmf_env() -> ProductEnvironment:
    return _build_env("vmf_config.yaml")


@pytest.fixture(scope="session")
def gfz_env() -> ProductEnvironment:
    return _build_env("gfz_config.yaml")


@pytest.fixture(scope="session")
def wuhan_qf(wuhan_env, workspace) -> QueryFactory:
    return QueryFactory(product_environment=wuhan_env, workspace=workspace)


@pytest.fixture(scope="session")
def cod_qf(cod_env, workspace) -> QueryFactory:
    return QueryFactory(product_environment=cod_env, workspace=workspace)


@pytest.fixture(scope="session")
def cddis_qf(cddis_env, workspace) -> QueryFactory:
    return QueryFactory(product_environment=cddis_env, workspace=workspace)


@pytest.fixture(scope="session")
def igs_qf(igs_env, workspace) -> QueryFactory:
    return QueryFactory(product_environment=igs_env, workspace=workspace)


@pytest.fixture(scope="session")
def vmf_qf(vmf_env, workspace) -> QueryFactory:
    return QueryFactory(product_environment=vmf_env, workspace=workspace)


@pytest.fixture(scope="session")
def gfz_qf(gfz_env, workspace) -> QueryFactory:
    return QueryFactory(product_environment=gfz_env, workspace=workspace)


@pytest.fixture(scope="session")
def fetcher() -> ResourceFetcher:
    return ResourceFetcher()


@pytest.fixture(scope="session")
def test_date() -> datetime.datetime:
    return TEST_DATE
