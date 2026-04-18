"""Test the fluent StationQuery builder for IGS RINEX v3.

Searches for IGS stations near Fairbanks, AK on 2026-04-15.
Demonstrates metadata lookup and remote file search via IGS network.

Usage:
    python dev/dev_igs_station_query.py
"""

import datetime
import logging

from gnss_product_management import GNSSClient

logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)-8s %(name)s  %(message)s",
)

date = datetime.datetime(2026, 4, 15, tzinfo=datetime.timezone.utc)
client = GNSSClient.from_defaults(base_dir="/tmp/gnss-igs-test")

# Fairbanks, AK — should find FAIR and nearby IGS stations
lat = 64.978
lon = -147.499
radius_km = 1000.0

# ── Build the query ───────────────────────────────────────────────────────
sq = (
    client.station_query()
    .networks("IGS")
    .within(lat, lon, radius_km)
    .rinex_version("3")
    .on(date)
)

# ── 1. Station metadata ──────────────────────────────────────────────────
print("\n── IGS station metadata ────────────────────────────────")
stations = sq.metadata()
for s in stations:
    dc = getattr(s, "data_center", "?")
    print(f"  {s.site_code:>4s}  ({s.lat:8.4f}, {s.lon:9.4f})  data_center={dc}")
if not stations:
    print("  (no stations found)")
print(f"\n  Total: {len(stations)} stations")

# ── 2. Remote search ─────────────────────────────────────────────────────
print("\n── Remote RINEX search ─────────────────────────────────")
results = sq.search()
for r in results:
    ssss = r.parameters.get("SSSS", "?")
    v = r.parameters.get("V", "?")
    print(f"  {ssss:>4s}  v{v}  {r.uri}")
if not results:
    print("  (no remote files found)")
print(f"\n  Total: {len(results)} results")
