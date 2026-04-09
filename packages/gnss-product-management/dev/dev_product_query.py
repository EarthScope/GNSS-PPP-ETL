from pathlib import Path
import datetime
import logging

from gnss_product_management import defaults, ProductQuery
from gnss_product_management.client import product_query
from gnss_product_management.environments import workspace
from gnss_product_management.factories.remote_transport import WormHole
from gnss_product_management.factories.search_planner import SearchPlanner

logging.basicConfig(level=logging.DEBUG)

work_space = defaults.DefaultWorkSpace
product_registry = defaults.DefaultProductEnvironment
base_dir = Path("/Users/franklyndunbar/Project/SeaFloorGeodesy/Data/GNSS-DATA")

work_space.register_spec(base_dir=base_dir, spec_ids=["local_config"], alias="local")

search_planner = SearchPlanner(product_registry=product_registry, workspace=work_space)
wormhole = WormHole(max_connections=10, product_registry=product_registry)

date = datetime.datetime(2025, 1, 2, tzinfo=datetime.timezone.utc)

query_agent = ProductQuery(wormhole=wormhole, search_planner=search_planner).on(date)


orbit_agent = (
    query_agent.for_product("ORBIT").where(TTT="FIN").sources("COD", "ESA").search()
)
print(f"Search results for ORBIT on {date.date()}:\n")
for r in orbit_agent:
    print(f"  [FOUND]   {r.hostname:<35s}  {r.filename}")

clock_agent = (
    query_agent.for_product("CLOCK").where(TTT="FIN").sources("COD", "ESA").search()
)
print(f"\nSearch results for CLOCK on {date.date()}:\n")
for r in clock_agent:
    print(f"  [FOUND]   {r.hostname:<35s}  {r.filename}")

erp_agent = (
    query_agent.for_product("ERP").where(TTT="FIN").sources("COD", "ESA").search()
)
print(f"\nSearch results for ERP on {date.date()}:\n")
for r in erp_agent:
    print(f"  [FOUND]   {r.hostname:<35s}  {r.filename}")

attobx_agent = query_agent.for_product("ATTOBX").search()
print(f"\nSearch results for ATTOBX on {date.date()}:\n")
for r in attobx_agent:
    print(f"  [FOUND]   {r.hostname:<35s} {r.directory:<35s} {r.filename}")
