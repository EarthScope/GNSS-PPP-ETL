import datetime
from pathlib import Path
import time
import logging

#logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

from gnss_ppp_products.environments import ProductEnvironment
from gnss_ppp_products.environments import WorkSpace
from gnss_ppp_products.factories.query_factory import QueryFactory
from gnss_ppp_products.factories.resource_fetcher import ResourceFetcher
from gnss_ppp_products.factories.dependency_resolver import DependencyResolver
from gnss_ppp_products.specifications.dependencies.dependencies import DependencySpec

from gnss_ppp_products.defaults import DefaultProductEnvironment, DefaultWorkSpace, Pride_PPP_task


env = DefaultProductEnvironment


workspace = DefaultWorkSpace


base_dir = Path("/Volumes/DunbarSSD/Project/SeafloorGeodesy/GNSS-PPP")
pride_dir = Path("/Volumes/DunbarSSD/Project/SeafloorGeodesy/SFGMain/Pride")
workspace.register_spec(base_dir=base_dir,spec_ids=["local_config"],alias="local")
workspace.register_spec(base_dir=pride_dir,spec_ids=["pride_config"],alias="pride")


    

dep_spec = Pride_PPP_task

qf = QueryFactory(
    product_environment=env,
    workspace=workspace,
    )
fetcher = ResourceFetcher(max_connections=10)

dep_res = DependencyResolver(
    dep_spec=dep_spec,
    product_environment=env,
    query_factory=qf,
    fetcher=fetcher,
)
from gnss_ppp_products.lockfile import DependencyLockFile
station = "TEST"
years = [2023,2024,2025]
months = [2,5,8]
days = [3,6,9]
days = [x+2 for x in days]
dates = [datetime.datetime(y, m, d, tzinfo=datetime.timezone.utc) for y in years for m in months for d in days]
dates = dates[2:]
times = []
for date in dates:
    start = time.time()
    resolution,dep_lockfile_path = dep_res.resolve(date=date,local_sink_id="local")
    end = time.time()
    times.append(end - start)
    print(f"Resolution for {date.date()} took {end - start:.2f} seconds.")
    print(f"\n{'='*60}\nDATE: {date.date()}\n{'='*60}")
    print(f"Table: {resolution.spec_name}")
    print(f"{resolution.table()}\n")
    #print(f"Lockfile:\n{resolution.to_lockfile().model_dump_json(indent=2)}\n\n")
    # if dep_lockfile_path:
    #     dlf = DependencyLockFile.model_validate_json(dep_lockfile_path.read_text(encoding="utf-8"))
    #     print(dlf.model_dump_json(indent=2))
print(f"\nAverage resolution time: {sum(times)/len(times):.2f} seconds.")