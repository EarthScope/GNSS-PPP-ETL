"""Demonstrate the two canonical download interfaces for queried products.

Pattern A — fluent one-shot (search + download in one call):

    paths = client.query("ORBIT").on(date).where(TTT="FIN").download(sink_id="local", limit=1)

Pattern B — two-step inspect-then-download:

    results = client.query("ORBIT").on(date).where(TTT="FIN").search()
    # inspect / filter results...
    paths = client.download(results[:1], sink_id="local")
"""

import datetime
import logging
from pathlib import Path

from gnss_product_management import GNSSClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

base_dir = Path("/Users/franklyndunbar/Project/SeaFloorGeodesy/Data/GNSS-DATA")
client = GNSSClient.from_defaults(base_dir=base_dir)
client.display()
date = datetime.datetime(2025, 1, 2, tzinfo=datetime.timezone.utc)
query_agent = client.query().on(date)

# --- Search only -----------------------------------------------------------

orbit_results = query_agent.for_product("ORBIT").where(TTT="FIN").sources("COD", "ESA").search()
print(f"Search results for ORBIT on {date.date()}:\n")
for r in orbit_results:
    print(f"  [FOUND]   {r.hostname:<35s}  {r.filename}")

clock_results = query_agent.for_product("CLOCK").where(TTT="FIN").sources("COD", "ESA").search()
print(f"\nSearch results for CLOCK on {date.date()}:\n")
for r in clock_results:
    print(f"  [FOUND]   {r.hostname:<35s}  {r.filename}")

erp_results = query_agent.for_product("ERP").where(TTT="FIN").sources("COD", "ESA").search()
print(f"\nSearch results for ERP on {date.date()}:\n")
for r in erp_results:
    print(f"  [FOUND]   {r.hostname:<35s}  {r.filename}")

attobx_results = query_agent.for_product("ATTOBX").search()
print(f"\nSearch results for ATTOBX on {date.date()}:\n")
for r in attobx_results:
    print(f"  [FOUND]   {r.hostname:<35s} {r.directory:<35s} {r.filename}")

# --- Pattern A: fluent one-shot download -----------------------------------
# Best when you don't need to inspect results first.

print("\n--- Pattern A: fluent one-shot download ---")
paths = (
    query_agent.for_product("ORBIT")
    .where(TTT="FIN")
    .sources("COD")
    .download(sink_id="local", limit=1)
)
for p in paths:
    print(f"  [DOWNLOADED]  {p}")

# --- Pattern B: two-step inspect-then-download ----------------------------
# Best when you want to filter or log results before committing to a download.

print("\n--- Pattern B: two-step inspect-then-download ---")
clock_results = query_agent.for_product("CLOCK").where(TTT="FIN").sources("COD").search()
best = [r for r in clock_results if r.protocol.lower() in ("ftp", "ftps", "https")][:1]
paths = client.download(best, sink_id="local")
for p in paths:
    print(f"  [DOWNLOADED]  {p}")
