import datetime
from email.mime import base
import json
from pathlib import Path

from annotated_types import T
from gnss_ppp_products.catalogs import dependency_resolver
from gnss_ppp_products.specifications.parameters.parameter import ParameterCatalog
from gnss_ppp_products.specifications.products.catalog import ProductSpecCatalog
import pytest

from gnss_ppp_products.factories import (
    ProductEnvironment,
    QueryFactory,
    ResourceFetcher,
)
from gnss_ppp_products.specifications.dependencies.dependencies import (
    DependencyResolution,
    DependencySpec,
    ResolvedDependency,
)
from gnss_ppp_products.specifications.dependencies.dependency_resolver import (
    DependencyResolver,
)
from gnss_ppp_products.specifications.dependencies.lockfile import (
    ProductLockfile,
)
from gnss_ppp_products.specifications.format.format_spec import FormatSpecCatalog

from gnss_ppp_products.specifications.remote.resource import ResourceCatalog
# ── Paths ──────────────────────────────────────────────────────────

_CONFIGS_DIR = (
    Path(__file__).resolve().parent.parent
    / "src" / "gnss_ppp_products" / "configs"
)
PRIDE_PPPAR_SPEC = _CONFIGS_DIR / "dependencies" / "pride_pppar.yaml"
META_SPEC_YAML = _CONFIGS_DIR / "meta" / "meta_spec.yaml"
PRODUCT_SPEC_YAML = _CONFIGS_DIR / "products" / "product_spec.yaml"
LOCAL_CONFIG = _CONFIGS_DIR / "local" / "local_config.yaml"
CENTERS_DIR = _CONFIGS_DIR / "centers"


parameter_catalog = ParameterCatalog.from_yaml(META_SPEC_YAML)
format_spec_catalog = FormatSpecCatalog.from_yaml(PRODUCT_SPEC_YAML)
product_spec_catalog = ProductSpecCatalog.from_yaml(PRODUCT_SPEC_YAML)

base_dir = Path("/Volumes/DunbarSSD/Project/SeafloorGeodesy/GNSS-PPP")

multi_env = ProductEnvironment.from_yaml(
    base_dir=base_dir,
    meta_spec_yaml=META_SPEC_YAML,
    product_spec_yaml=PRODUCT_SPEC_YAML,
    local_config=str(LOCAL_CONFIG),
    remote_specs=list(CENTERS_DIR.glob("*.yaml")),
)

dep_spec = DependencySpec.from_yaml(PRIDE_PPPAR_SPEC)

qf = QueryFactory(
        remote_factory=multi_env.remote_factory,
        local_factory=multi_env.local_factory,
        product_catalog=multi_env.product_catalog,
        parameter_catalog=multi_env.parameter_catalog,
    )
fetcher = ResourceFetcher(ftp_timeout=30)

dep_res = DependencyResolver(
    dep_spec=dep_spec,
    base_dir=base_dir,
    query_factory=qf,
    fetcher=fetcher,
)

years = [2023,2024,2025]
months = [1,3,6,9]
days = [1,15,28]
dates = [datetime.datetime(y, m, d, tzinfo=datetime.timezone.utc) for y in years for m in months for d in days]


for date in dates:
    resolution = dep_res.resolve(date=date,download=True)
    print(f"\n{'='*60}\nDATE: {date.date()}\n{'='*60}")
    print(f"Table: {resolution.spec_name}")
    print(f"{resolution.table()}\n")
    print(f"Lockfile:\n{resolution.to_lockfile().model_dump_json(indent=2)}\n\n")
