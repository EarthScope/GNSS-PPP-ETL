"""Test the StationQuery builder for CORS, ERT, and IGS networks.

Searches for stations near Fairbanks, AK on 2026-04-15.
Uses RINEX v3 with automatic v2 fallback for stations that have no v3 data.

Usage:
    python dev/dev_cors_station_query.py
"""

import datetime
import logging

from gnss_product_management import GNSSClient

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s %(name)s  %(message)s",
)
logging.getLogger("fsspec").setLevel(logging.WARNING)
logging.getLogger("remote_transport").setLevel(logging.WARNING)

date = datetime.datetime(2026, 4, 15, tzinfo=datetime.timezone.utc)
client = GNSSClient.from_defaults(
    base_dir="/Volumes/DunbarSSD/Project/SeafloorGeodesy/GNSS-PPP"
)

# Fairbanks, AK
lat = 64.978
lon = -147.499
radius_km = 2000.0

networks = ["CORS", "ERT", "IGS"]

base_query = (
    client.station_query()
    .rinex_version("3")
    .with_version_fallback()
    .on(date)
    .within(lat, lon, radius_km)
)

for network in networks:
    sq = base_query.networks(network)
    stations = sq.metadata()
    print(f"\n{'='*60}")
    print(f"  Network: {network}  ({len(stations)} stations in spatial query)")
    print(f"{'='*60}")
    for s in stations:
        dc = getattr(s, "data_center", "?")
        print(f"  {s.site_code:>6s}  ({s.lat:8.4f}, {s.lon:9.4f})  data_center={dc}")
    if not stations:
        print("  (no stations found)")

    results = sq.download("local")
    print(f"\n  Downloaded: {len(results)}/{len(stations)} stations")
    for r in results:
        v = r.parameters.get("V", "?")
        print(f"    {r.parameters.get('SSSS','?'):>6s}  v{v}  {r.uri}")
