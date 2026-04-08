"""Download products for a specific center and product type."""

import datetime
from pathlib import Path
from gnss_product_management import GNSSClient

base_dir = Path(
    "/Users/franklyndunbar/Project/SeaFloorGeodesy/Data/GNSS-DATA"
)  # <-- change to your path
client = GNSSClient.from_defaults(base_dir=base_dir)

date = datetime.datetime(2025, 1, 2, tzinfo=datetime.timezone.utc)

paths = (
    client.query("CLOCK")
    .on(date)
    .where(TTT="FIN")
    .sources("COD", "ESA", "IGS")
    .prefer(TTT=["FIN", "RAP", "ULT"])
    .download(sink_id="local", limit=1)
)

if paths:
    print(f"Downloaded to: {paths[0]}")
else:
    print("No products found.")
