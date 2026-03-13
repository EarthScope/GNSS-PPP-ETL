"""Quick smoke test for the new assets/rinex/ package."""
import datetime

from gnss_ppp_products.assets.rinex.base import RinexBase, _RegexFallbackDict
from gnss_ppp_products.assets.rinex.query import RinexFileQuery
from gnss_ppp_products.assets.rinex.config import (
    RinexConfig,
    StationConfig,
    MonumentConfig,
    ReceiverConfig,
    RegionConfig,
    SatelliteSystemConfig,
    SampleIntervalConfig,
    DurationConfig,
)

# Test query building
q = RinexFileQuery(
    date=datetime.datetime(2024, 1, 15, tzinfo=datetime.timezone.utc),
    station="BRDC",
    monument=0,
    receiver="0",
    region="IGS",
    satellite_system="M",
    content="N",
    data_source="R",
)
q.build_filename(
    "{station}{monument}{receiver}{region}_{data_source}_{year}{doy}0000_{duration}_{satellite_system}{content}.rnx.*"
)
q.build_directory("pub/igs/data/{year}/{doy}/")
print("Filename:", q.filename)
print("Directory:", q.directory)

# Test config build
cfg = RinexConfig(
    id="test_nav",
    content="N",
    server_id="ign_ftp",
    station_set=[StationConfig(station="BRDC")],
    monument_set=[MonumentConfig(monument=0)],
    receiver_set=[ReceiverConfig(receiver="0")],
    region_set=[RegionConfig(region="IGS")],
    sampling_set=[SampleIntervalConfig(interval="01D")],
    satellite_system_set=[SatelliteSystemConfig(satellite_system="M")],
    duration_set=[DurationConfig(duration="01D")],
    directory="pub/igs/data/{year}/{doy}/",
    filename="{station}{monument}{receiver}{region}_{data_source}_{year}{doy}0000_{duration}_{satellite_system}{content}.rnx.*",
)
queries = cfg.build(datetime.datetime(2024, 1, 15, tzinfo=datetime.timezone.utc))
for q in queries:
    print(f"  {q.filename}  |  {q.directory}")

print("\nAll OK")
