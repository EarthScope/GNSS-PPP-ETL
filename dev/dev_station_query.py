"""Test the fluent StationQuery builder for EarthScope RINEX v3.

Searches for station AB04 on 2025-01-01 via the EarthScope (ERT) network.
Demonstrates metadata lookup, remote file search, and (optionally) download.

Requires EARTHSCOPE_TOKEN to be set for the remote search to succeed:
    export EARTHSCOPE_TOKEN=<your-token>
    python dev/dev_station_query.py

Usage:
    python dev/dev_station_query.py
"""

import datetime
import logging

from gnss_product_management import GNSSClient

logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)-8s %(name)s  %(message)s",
)

date = datetime.datetime(2026, 4, 15, tzinfo=datetime.timezone.utc)
client = GNSSClient.from_defaults(base_dir="/Volumes/DunbarSSD/Project/SeafloorGeodesy/GNSS-PPP")

lat = 37.74387
lon = -105.49852
radius_m = 100000000
# ── Build the query ───────────────────────────────────────────────────────
sq = (
    client.station_query()
    .networks("ERT")
    .within(lat, lon, radius_m / 1000)
    .rinex_version("3")
    .on(date)
)


# ── 2. Remote search ─────────────────────────────────────────────────────
print("\n── Remote RINEX search ──────────────────────────────────")
results = sq.search()
for r in results:
    print(f"  {r.parameters.get('SSSS', '?'):>4s}  v{r.parameters.get('V', '?')}  {r.uri}")
if not results:
    print("  (no remote files found)")


sq.download(sink_id="local")
# ── 3. Download (uncomment to test) ──────────────────────────────────────
# To actually download, create the client with a base_dir:
#
#   from pathlib import Path
#   client = GNSSClient.from_defaults(base_dir=Path.home() / "gnss-data")
#   downloaded = sq.download(sink_id="local")
#   for fr in downloaded:
#       print(f"  {fr.parameters.get('SSSS')}  → {fr.local_path}")
