import datetime
import logging
import time
from pathlib import Path

from gnss_product_management import GNSSClient
from gnss_product_management.defaults import DefaultProductEnvironment, DefaultWorkSpace

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
# logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

# Paths to pride-ppp config files (relative to this dev script)
_pride_ppp_configs = Path(__file__).parents[2] / "pride-ppp" / "src" / "pride_ppp" / "configs"

workspace = DefaultWorkSpace
workspace.add_resource_spec(_pride_ppp_configs / "local" / "pride_config.yaml")

base_dir = Path.home() / "gnss-data"  # update for your environment
pride_dir = Path.home() / "pride"  # update for your environment
workspace.register_spec(base_dir=base_dir, spec_ids=["local_config"], alias="local")
workspace.register_spec(base_dir=pride_dir, spec_ids=["pride_config"], alias="pride")

DefaultProductEnvironment.add_resource_spec(
    _pride_ppp_configs / "centers" / "pride_table_config.yaml"
)
DefaultProductEnvironment.add_product_spec(
    _pride_ppp_configs / "products" / "pride_product_spec.yaml",
    id="pride_products",
)
DefaultProductEnvironment.build()

client = GNSSClient(
    product_registry=DefaultProductEnvironment,
    workspace=workspace,
    max_connections=10,
)

dep_spec_path = str(_pride_ppp_configs / "dependencies" / "pride_pppar.yaml")

station = "TEST"
years = [2023, 2024, 2025]
months = [2, 5, 8]
days = [3, 6, 9]
days = [x + 3 for x in days]
dates = [
    datetime.datetime(y, m, d, tzinfo=datetime.timezone.utc)
    for y in years
    for m in months
    for d in days
]
dates = dates[2:]
times = []
for date in dates:
    start = time.time()
    resolution, dep_lockfile_path = client.resolve_dependencies(
        dep_spec_path, date, sink_id="pride"
    )
    end = time.time()
    times.append(end - start)
    print(f"Resolution for {date.date()} took {end - start:.2f} seconds.")
    print(f"\n{'=' * 60}\nDATE: {date.date()}\n{'=' * 60}")
    print(f"Table: {resolution.spec_name}")
    print(f"{resolution.table()}\n")
print(f"\nAverage resolution time: {sum(times) / len(times):.2f} seconds.")
