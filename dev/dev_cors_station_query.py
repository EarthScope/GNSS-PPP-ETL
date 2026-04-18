"""Test the StationQuery builder for CORS, ERT, and IGS networks.

Searches for stations near Fairbanks, AK on 2026-04-15.
Uses RINEX v3 with automatic v2 fallback for stations that have no v3 data.

Usage:
    python dev/dev_cors_station_query.py
"""

import datetime
import logging
from pathlib import Path

from gnss_product_management import GNSSClient
from pride_ppp import PrideProcessor

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s %(name)s  %(message)s",
)
logging.getLogger("fsspec").setLevel(logging.WARNING)
logging.getLogger("remote_transport").setLevel(logging.WARNING)

date = datetime.datetime(2026, 1, 4, tzinfo=datetime.timezone.utc)
client = GNSSClient.from_defaults(
    base_dir="/Volumes/DunbarSSD/Project/SeafloorGeodesy/GNSS-PPP", max_connections=15
)

# Fairbanks, AK
lat = 64.978
lon = -147.499
radius_km = 20000.0

networks = ["IGS", "ERT", "CORS"]
versions = ["3", "2"]  # try v3 first, then fallback to v2 if no stations found

base_query = client.station_query().on(date).within(lat, lon, radius_km)

for version in versions:
    sq = base_query.rinex_version(version)
    stations = sq.metadata()
    print(f"\n{'=' * 60}")
    print(f"  ({len(stations)} stations in spatial query)")
    print(f"{'=' * 60}")
    for s in stations:
        dc = getattr(s, "data_center", "?")
        # print(f"  {s.site_code:>6s}  ({s.lat:8.4f}, {s.lon:9.4f})  data_center={dc}")
    if not stations:
        print("  (no stations found)")

    results = sq.download("local", max_workers=200)
    print(f"\n  Downloaded: {len(results)}/{len(stations)} stations")


target_dir = Path("/Volumes/DunbarSSD/Project/SeafloorGeodesy/GNSS-PPP/2026/004/rinex")
output_dir = target_dir / "pride_output"
output_dir.mkdir(exist_ok=True)
processor = PrideProcessor(
    pride_dir=Path("/Volumes/DunbarSSD/Project/SeafloorGeodesy/GNSS-PPP")
    / "Pride",  # update for your environment
    output_dir=output_dir,  # update for your environment
)

# results = processor.process_batch(list(target_dir.glob("*")), max_workers=50)
# # --- 4. Summarise results ------------------------------------------------
# for r in results:
#     status = "OK" if r.success else "FAIL"
#     print(f"  [{status}] {r.rinex_path.name}  site={r.site}  date={r.date}")

# succeeded = [r for r in results if r.success]
# failed = [r for r in results if not r.success]
# print(f"\n{len(succeeded)} succeeded, {len(failed)} failed")
