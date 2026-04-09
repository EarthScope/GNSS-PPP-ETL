"""Download products for a specific center and product type."""

import datetime
from pathlib import Path
from gnss_product_management import GNSSClient

base_dir = Path(
    "/Users/franklyndunbar/Project/SeaFloorGeodesy/Data/GNSS-DATA"
)  # <-- change to your path
client = GNSSClient.from_defaults(base_dir=base_dir)

date = datetime.datetime(2025, 1, 2, tzinfo=datetime.timezone.utc)

queries = (
    client.query()
    .on(date)
    .for_product("ORBIT")
    .where(TTT="FIN")
    .sources("COD", "ESA", "IGS")
    .prefer(TTT=["FIN", "RAP", "ULT"])
    .search()
)

if queries:
    print(f"Found {len(queries)} queries.")
else:
    print("No products found.")
