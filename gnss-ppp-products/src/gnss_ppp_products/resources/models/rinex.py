"""
RINEX filename queries and RINEX-specific YAML configuration schemas.
"""

import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, field_serializer

from ..remote.utils import _parse_date, _date_to_gps_week
from ..igs_conventions import (
    ProductSampleInterval,
    ProductDuration,
    Rinex3DataType,
    Rinex3DataSource,
    Rinex2DataType,
    Rinex2FileInterval,
    RinexSatelliteSystem,
    RinexVersion,
)

from .server import Server
# ---------------------------------------------------------------------------
# Regex fallback patterns for RINEX filename placeholders
# ---------------------------------------------------------------------------

_RINEX_PLACEHOLDER_REGEX: dict[str, str] = {
    "station":          r"[A-Z0-9]{4}",
    "monument":         r"\d",
    "receiver":         r"[A-Z0-9]",
    "region":           r"[A-Z]{3}",
    "data_source":      r"[A-Z]",
    "year":             r"\d{4}",
    "doy":              r"\d{3}",
    "duration":         r"\d{2}[SMHD]",
    "interval":         r"\d{2}[SMHD]",
    "satellite_system": r"[GRECJILM]",
    "content":          r"[A-Z]",
    "gps_week":         r"\d{4}",
    "yy":               r"\d{2}",
    "month":            r"\d{2}",
    "day":              r"\d{2}",
}


class _RinexRegexFallbackDict(dict):
    """Dict that returns regex patterns for unknown RINEX placeholder keys."""

    def __missing__(self, key: str) -> str:
        return _RINEX_PLACEHOLDER_REGEX.get(key, ".+")


# ---------------------------------------------------------------------------
# RINEX filename query
# ---------------------------------------------------------------------------


class RinexFileQuery(BaseModel):
    date: Optional[datetime.datetime | datetime.date] = None
    server: Optional[Server] = None
    station: Optional[str] = None
    region: Optional[str] = None
    monument: Optional[int] = None
    receiver: Optional[str] = None
    interval: Optional[ProductSampleInterval | Rinex2FileInterval] = None
    duration: Optional[ProductDuration | Rinex2FileInterval] = None
    satellite_system: Optional[RinexSatelliteSystem] = None
    content: Optional[Rinex3DataType | Rinex2DataType] = None
    filename: Optional[str] = None
    directory: Optional[str] = None
    version: RinexVersion = RinexVersion.V3
    data_source: Optional[Rinex3DataSource] = Rinex3DataSource.R

    @field_serializer("date")
    def _serialize_date(self, date: Optional[datetime.datetime | datetime.date]) -> Optional[str]:
        if date is None:
            return None
        return date.astimezone(datetime.timezone.utc).isoformat()
    
    @field_validator("date")
    def _validate_date(cls, date: Optional[datetime.datetime | datetime.date]) -> Optional[datetime.datetime | datetime.date]:
        if date is None:
            return None
        if isinstance(date, str):
            return datetime.datetime.fromisoformat(date).astimezone(datetime.timezone.utc)
        return date
    @classmethod
    def _from_filename_v3_v4(cls, filename: str) -> "RinexFileQuery":
        '''
        Observation and Meteorological Files

        SSSSMRCCC_S_YYYYDDDHHMM_DDU_FRU_DT.fff.cmp

        Navigation Files

        SSSSMRCCC_S_YYYYDDDHHMM_DDU_DT.fff.cmp
        
        '''
        # Detect if we are parsing an observation/meteorological file or a navigation file
        segments = filename.split("_")
        if len(segments) == 5:
            # Navigation file format
            station_region, data_source,yeardoy,coverage, satellite_system_ext = segments
            content_type = Rinex3DataType.NAV
        elif len(segments) == 6:
            # Observation or meteorological file format
             station_region, data_source,yeardoy,coverage,interval, satellite_system_ext = segments
             content_type = Rinex3DataType.OBS if "O" in satellite_system_ext else Rinex3DataType.MET
        else:
            raise ValueError(f"Filename '{filename}' does not match expected RINEX formats")
        
        station = station_region[:4]
        monument = station_region[4]
        receiver = station_region[5]
        region = station_region[6:]

        data_source = data_source[0]  # First character indicates data source

        year = int(yeardoy[:4])
        doy = int(yeardoy[4:7])
        hour = int(yeardoy[7:9])
        minute = int(yeardoy[9:11])
        date = datetime.datetime(year, 1, 1) + datetime.timedelta(days=doy-1, hours=hour, minutes=minute)

        coverage = ProductDuration(coverage)
        if content_type != Rinex3DataType.NAV:
            interval = ProductSampleInterval(interval)
        else:
            interval = None  # Navigation files do not have a sample interval field

        satellite_system = RinexSatelliteSystem(satellite_system_ext[0])  # First character indicates satellite system
        content_type = Rinex3DataType(satellite_system_ext[1:])  # Remaining characters indicate content type
        return cls(
            date=date,
            station=station,
            region=region,
            monument=monument,
            receiver=receiver,
            interval=interval,
            duration=coverage,
            satellite_system=satellite_system,
            content=content_type,
            filename=filename,
            version=RinexVersion.V3
        )
    
    @classmethod
    def _from_filename_v2(cls,filename:str) -> "RinexFileQuery":
        '''
        ssssdddf.yyt
        ssss: 4-character station code
        ddd: 3-digit day of year (001-366)
        f: file sequence number/character within day
            File sequence number/character within day
            Daily files (30 seconds): f=0
            Hourly files (30 seconds):
            f=a (00:00:00 to 00:59:30),
            f=b (01:00:00 to 01:59:30),
            ...
            f=x (23:00:00 to 23:59:30)
            High-rate files (15M, 1 Hz):
            f=a00 (00:00:00 to 00:14:59)
            f=a15 (00:15:00 to 00:29:59) ...
            f=m30 (12:30:00 to 12:44:59) ...
            f=x45 (23:45:00 to 23:59:59)
        yy: 2-digit year
        t: file type
            O: Observation file
            D: Hatanaka compressed observation file
            N: GPS navigation file
            G: GLONASS navigation file
            M: Meteorological file
        '''
        name,ext = filename.split(".")
        station = name[:4]
        doy = name[4:7]
        file_seq = Rinex2FileInterval(name[7:])
        yy = name[-2:]
        v2_type = Rinex2DataType(name[-1])
        date = datetime.datetime(
            year=int("20"+yy),
            month=1,
            day=1
        ) + datetime.timedelta(days=int(doy)-1)
        match v2_type:
            case Rinex2DataType.GLONASS_NAV:
                satellite_system = RinexSatelliteSystem.GLONASS
            case Rinex2DataType.GALILEO_NAV:
                satellite_system = RinexSatelliteSystem.GALILEO
            case _:
                satellite_system = None

        return cls(
            date=date,
            station=station,
            interval = file_seq,
            content = v2_type,
            version = RinexVersion.V2,
            filename=filename,
            satellite_system=satellite_system
        )


    @classmethod
    def from_filename(cls, filename: str) -> "RinexFileQuery":
        # determine if this is a RINEX v3/v4 filename or a RINEX v2 filename
        if len(filename.split("_")) > 2:
            return cls._from_filename_v3_v4(filename)
        else:
            return cls._from_filename_v2(filename)

    # -- substitution helpers ------------------------------------------------

    def _substitution_map(self) -> dict[str, str]:
        """Collect known field values as a ``{placeholder: value}`` mapping."""
        subs: dict[str, str] = {}
        if self.date is not None:
            year, doy = _parse_date(self.date)
            subs["year"] = year
            subs["doy"] = doy
            subs["gps_week"] = str(_date_to_gps_week(self.date))
            subs["yy"] = str(self.date.year)[-2:]
            subs["month"] = f"{self.date.month:02d}"
            subs["day"] = f"{self.date.day:02d}"
        if self.station is not None:
            subs["station"] = self.station
        if self.monument is not None:
            subs["monument"] = str(self.monument)
        if self.receiver is not None:
            subs["receiver"] = self.receiver
        if self.region is not None:
            subs["region"] = self.region
        if self.data_source is not None:
            subs["data_source"] = self.data_source.value
        if self.interval is not None:
            subs["interval"] = self.interval.value
        if self.duration is not None:
            subs["duration"] = self.duration.value
        if self.satellite_system is not None:
            subs["satellite_system"] = self.satellite_system.value
        if self.content is not None:
            subs["content"] = self.content.value
        return subs

    def build_query(self, template: str) -> str:
        """
        Build a filename pattern from a template string.

        Known field values are substituted literally; missing fields
        become regex patterns suitable for matching against directory
        listings.
        """
        return template.format_map(_RinexRegexFallbackDict(self._substitution_map()))

    def build_directory(self, template: str) -> str:
        """Build a directory path from a template, substituting known values."""
        return template.format_map(_RinexRegexFallbackDict(self._substitution_map()))


# ---------------------------------------------------------------------------
# RINEX YAML configuration schemas
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

class RinexConfig(BaseModel):
    id: str
    content: Rinex3DataType | Rinex2DataType
    server_id: Optional[str] = None
    version: Optional[RinexVersion] = RinexVersion.V3
    available: bool = True
    description: Optional[str] = None
    data_source: Optional[Rinex3DataSource] = Rinex3DataSource.R
    station_set: List[StationConfig]
    monument_set: List[MonumentConfig]
    receiver_set: List[ReceiverConfig]
    region_set: List[RegionConfig]
    sampling_set: List["SampleIntervalConfig"]
    satellite_system_set: List[SatelliteSystemConfig]
    duration_set: List["DurationConfig"]
    directory: str
    filename: str

    def build(self, date: datetime.datetime | datetime.date) -> List[RinexFileQuery]:
        """Expand config into all combinations of station/monument/receiver/region/sat-sys/sampling/duration."""
        queries: list[RinexFileQuery] = []
        stations = [s.station for s in self.station_set] or [None]
        monuments = [m.monument for m in self.monument_set] or [None]
        receivers = [r.receiver for r in self.receiver_set] or [None]
        regions = [r.region for r in self.region_set] or [None]
        sat_systems = [s.satellite_system for s in self.satellite_system_set] or [None]
        samplings = [s.interval for s in self.sampling_set] or [None]
        durations = [d.duration for d in self.duration_set] or [None]
        for station in stations:
            for monument in monuments:
                for receiver in receivers:
                    for region in regions:
                        for sat_sys in sat_systems:
                            for sampling in samplings:
                                for duration in durations:
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
                                    query.filename = query.build_query(self.filename)
                                    query.directory = query.build_directory(self.directory)
                                    queries.append(query)
        return queries
from .products import SampleIntervalConfig, DurationConfig  # noqa: E402
RinexConfig.model_rebuild()
