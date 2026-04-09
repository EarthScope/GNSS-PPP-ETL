"""Search for GNSS products on remote analysis center servers."""

import datetime
from gnss_product_management import GNSSClient

client = GNSSClient.from_defaults(
    base_dir="/Users/franklyndunbar/Project/SeaFloorGeodesy/Data/GNSS-DATA"
)

date = datetime.datetime(2025, 8, 11, tzinfo=datetime.timezone.utc)
query_agent = client.query().on(date)

orbit_search = query_agent.for_product("ORBIT").search()

print(f"Search results for ORBIT on {date.date()}:\n")
for r in orbit_search:
    print(f"  [FOUND]   {r.hostname:<35s}  {r.filename}")

clock_search = query_agent.for_product("CLOCK").search()
print(f"\nSearch results for CLOCK on {date.date()}:\n")
for r in clock_search:
    print(f"  [FOUND]   {r.hostname:<35s}  {r.filename}")

bias_search = query_agent.for_product("BIA").search()
print(f"\nSearch results for BIA on {date.date()}:\n")
for r in bias_search:
    print(f"  [FOUND]   {r.hostname:<35s}  {r.filename}")

erp_search = query_agent.for_product("ERP").search()
print(f"\nSearch results for ERP on {date.date()}:\n")
for r in erp_search:
    print(f"  [FOUND]   {r.hostname:<35s}  {r.filename}")
