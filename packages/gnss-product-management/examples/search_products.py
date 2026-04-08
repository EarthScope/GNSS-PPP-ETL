"""Search for GNSS products on remote analysis center servers."""

import datetime
from gnss_product_management import GNSSClient

client = GNSSClient.from_defaults(
    base_dir="/Users/franklyndunbar/Project/SeaFloorGeodesy/Data/GNSS-DATA"
)

date = datetime.datetime(2025, 1, 2, tzinfo=datetime.timezone.utc)
results = client.query("ORBIT").on(date).search()

print(f"Search results for ORBIT on {date.date()}:\n")
for r in results:
    print(f"  [FOUND]   {r.hostname:<35s}  {r.filename}")

client.download(results[0:1], date=date, sink_id="local")
