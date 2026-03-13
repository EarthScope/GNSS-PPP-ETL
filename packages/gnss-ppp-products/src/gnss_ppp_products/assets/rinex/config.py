import datetime
from itertools import product
from typing import List, Optional

from pydantic import BaseModel

from ..base.config import SampleIntervalConfig, DurationConfig
from ..base.igs_conventions import RinexSatelliteSystem
from .base import RinexBase
from .query import RinexFileQuery


# ---------------------------------------------------------------------------
# RINEX-specific YAML configuration schemas
# ---------------------------------------------------------------------------


class StationConfig(BaseModel):
    station: str
    description: Optional[str] = None


class MonumentConfig(BaseModel):
    monument: int
    description: Optional[str] = None


class ReceiverConfig(BaseModel):
    receiver: str
    description: Optional[str] = None


class RegionConfig(BaseModel):
    region: str
    description: Optional[str] = None


class SatelliteSystemConfig(BaseModel):
    satellite_system: RinexSatelliteSystem
    description: Optional[str] = None


class RinexConfig(RinexBase):
    """Configuration for a RINEX product."""

    id: str
    server_id: Optional[str] = None
    available: bool = True
    station_set: List[StationConfig]
    monument_set: List[MonumentConfig]
    receiver_set: List[ReceiverConfig]
    region_set: List[RegionConfig]
    sampling_set: List[SampleIntervalConfig]
    satellite_system_set: List[SatelliteSystemConfig]
    duration_set: List[DurationConfig]

    def build(self, date: datetime.datetime | datetime.date) -> List[RinexFileQuery]:
        """Expand config into all combinations of station/monument/receiver/region/sat-sys/sampling/duration."""
        assert self.filename is not None, "RinexConfig must have a filename template"
        assert self.directory is not None, "RinexConfig must have a directory template"

        stations = [s.station for s in self.station_set] or [None]
        monuments = [m.monument for m in self.monument_set] or [None]
        receivers = [r.receiver for r in self.receiver_set] or [None]
        regions = [r.region for r in self.region_set] or [None]
        sat_systems = [s.satellite_system for s in self.satellite_system_set] or [None]
        samplings = [s.interval for s in self.sampling_set] or [None]
        durations = [d.duration for d in self.duration_set] or [None]

        queries: list[RinexFileQuery] = []
        for station, monument, receiver, region, sat_sys, sampling, duration in product(
            stations, monuments, receivers, regions, sat_systems, samplings, durations,
        ):
            query = RinexFileQuery(
                date=date,
                station=station,
                monument=monument,
                receiver=receiver,
                region=region,
                satellite_system=sat_sys,
                interval=sampling,
                duration=duration,
                content=self.content,
                data_source=self.data_source,
            )
            query.build_filename(self.filename)
            query.build_directory(self.directory)
            queries.append(query)
        return queries

    def __init__(self, **data):
        super().__init__(**data)
       