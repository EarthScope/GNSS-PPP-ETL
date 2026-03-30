"""Search for GNSS products on remote analysis center servers.

Uses the default product environment (bundled YAML specs for all
registered analysis centers) to query for precise orbit (SP3) files
on a given date and prints which servers have matching files.
"""

import datetime
from gnss_product_management import QueryFactory, ResourceFetcher
from gnss_product_management.defaults import DefaultProductEnvironment, DefaultWorkSpace

# --- 1. Use pre-built environment and workspace -------------------------
env = DefaultProductEnvironment
workspace = DefaultWorkSpace

# --- 2. Create a query factory ------------------------------------------
qf = QueryFactory(product_environment=env, workspace=workspace)

# --- 3. Search for Final SP3 orbits on 2 Jan 2025 -----------------------
date = datetime.datetime(2025, 1, 2, tzinfo=datetime.timezone.utc)

queries = qf.get(
    date=date,
    product={"name": "ORBIT"},
)

fetcher = ResourceFetcher(max_connections=4)
results = fetcher.search(queries)

# --- 4. Print results ----------------------------------------------------
print(f"Search results for ORBIT on {date.date()}:\n")
for r in results:
    server = r.query.server.hostname
    if r.found:
        print(f"  [FOUND]   {server:<35s} {r.matched_filenames}")
    elif r.error:
        print(f"  [ERROR]   {server:<35s} {r.error}")
    else:
        print(f"  [MISS]    {server}")
