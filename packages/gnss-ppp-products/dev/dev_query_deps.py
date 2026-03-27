import datetime
from email.mime import base
import json
from pathlib import Path
import time
import logging
#logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

from gnss_ppp_products.factories.environment import ProductEnvironment
from gnss_ppp_products.factories.workspace import WorkSpace
from gnss_ppp_products.factories.query_factory import QueryFactory
from gnss_ppp_products.factories.resource_fetcher import ResourceFetcher
from gnss_ppp_products.factories.dependency_resolver import DependencyResolver
from gnss_ppp_products.specifications.dependencies.dependencies import DependencySpec

from gnss_ppp_products.configs import (
    META_SPEC_YAML,
    FORMAT_SPEC_YAML,
    PRODUCT_SPEC_YAML,
    LOCAL_SPEC_DIR,
    CENTERS_RESOURCE_DIR,
    DEPENDENCY_SPEC_DIR,
)
_CONFIGS_DIR = (
    Path(__file__).resolve().parent.parent
    / "src" / "gnss_ppp_products" / "configs"
)
PRIDE_PPPAR_SPEC = _CONFIGS_DIR / "dependencies" / "pride_pppar.yaml"
META_SPEC_YAML = _CONFIGS_DIR / "meta" / "meta_spec.yaml"
PRODUCT_SPEC_YAML = _CONFIGS_DIR / "products" / "product_spec.yaml"
LOCAL_CONFIG = _CONFIGS_DIR / "local" / "local_config.yaml"
CENTERS_DIR = _CONFIGS_DIR / "centers"



env = ProductEnvironment()
env.add_parameter_spec(META_SPEC_YAML)
env.add_format_spec(FORMAT_SPEC_YAML)
env.add_product_spec(PRODUCT_SPEC_YAML)
for path in Path(CENTERS_RESOURCE_DIR).glob("*.yaml"):
    env.add_resource_spec(path)
env.build()

workspace = WorkSpace()
for path in Path(LOCAL_SPEC_DIR).glob("*.yaml"):
    workspace.add_resource_spec(path)

base_dir = Path("/Volumes/DunbarSSD/Project/SeafloorGeodesy/GNSS-PPP")
pride_dir = Path("/Volumes/DunbarSSD/Project/SeafloorGeodesy/SFGMain/Pride")
workspace.register_spec(base_dir=base_dir,spec_ids=["local_config"],alias="local")
workspace.register_spec(base_dir=pride_dir,spec_ids=["pride_config"],alias="pride")


    

dep_spec = DependencySpec.from_yaml(PRIDE_PPPAR_SPEC)

qf = QueryFactory(
    product_environment=env,
    workspace=workspace,
    )
fetcher = ResourceFetcher(ftp_timeout=10)

dep_res = DependencyResolver(
    dep_spec=dep_spec,
    product_environment=env,
    query_factory=qf,
    fetcher=fetcher,
)

years = [2023,2024,2025]
months = [1,3,6,9]
days = [1,15,28]
dates = [datetime.datetime(y, m, d, tzinfo=datetime.timezone.utc) for y in years for m in months for d in days]


for date in dates:
    start = time.time()
    resolution = dep_res.resolve(date=date,local_sink_id="local")
    end = time.time()
    print(f"Resolution for {date.date()} took {end - start:.2f} seconds.")
    print(f"\n{'='*60}\nDATE: {date.date()}\n{'='*60}")
    print(f"Table: {resolution.spec_name}")
    print(f"{resolution.table()}\n")
    print(f"Lockfile:\n{resolution.to_lockfile().model_dump_json(indent=2)}\n\n")
