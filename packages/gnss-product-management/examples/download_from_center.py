"""Download products for a specific center and product type."""

import datetime
from pathlib import Path
from gnss_product_management import GNSSClient

base_dir = Path(
    "/Users/franklyndunbar/Project/SeaFloorGeodesy/Data/GNSS-DATA"
)  # <-- change to your path
client = GNSSClient.from_defaults(base_dir=base_dir)

date = datetime.datetime(2025, 1, 2, tzinfo=datetime.timezone.utc)
results = client.search(date, product="CLOCK", parameters={"TTT": "FIN"})[0:1]

print(f"Searching for COD CLOCK products on {date.date()}...\n")
paths = client.download(results, sink_id="local", date=date)

if paths:
    print(f"Downloaded to: {paths[0]}")
else:
    print("No products found.")
