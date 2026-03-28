"""Download products for a specific center and product type.

Shows how to constrain queries to a single analysis center (e.g. COD)
and a single product type, then download matched files to a local
workspace directory.
"""

import datetime
from pathlib import Path
from gnss_ppp_products import QueryFactory, ResourceFetcher
from gnss_ppp_products.defaults import DefaultProductEnvironment, DefaultWorkSpace

# --- 1. Set up environment and workspace ---------------------------------
env = DefaultProductEnvironment
workspace = DefaultWorkSpace

base_dir = Path("/data/gnss-products")  # <-- change to your path
workspace.register_spec(base_dir=base_dir, spec_ids=["local_config"], alias="local")

qf = QueryFactory(product_environment=env, workspace=workspace)
fetcher = ResourceFetcher(max_connections=4)

# --- 2. Query for COD clock files ----------------------------------------
date = datetime.datetime(2025, 1, 2, tzinfo=datetime.timezone.utc)

queries = qf.get(
    date=date,
    product={"name": "CLOCK"},
    parameters={"AAA": "COD"},  # constrain to CODE analysis center
)

# --- 3. Search remote servers --------------------------------------------
results = fetcher.search(queries)

for r in results:
    if r.found:
        print(f"Found: {r.query.server.hostname} — {r.matched_filenames}")

        # --- 4. Download to local workspace ------------------------------
        downloaded = fetcher.download_one(
            query=r.query,
            local_resource_id="local",
            local_factory=qf._local,
            date=date,
        )
        if downloaded:
            print(f"Downloaded to: {downloaded}")
