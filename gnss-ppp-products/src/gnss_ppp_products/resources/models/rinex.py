"""
RINEX filename queries and RINEX-specific YAML configuration schemas.
"""

import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

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


# ---------------------------------------------------------------------------
# RINEX filename query
# ---------------------------------------------------------------------------


class RinexFileQuery(BaseModel):
    date: Optional[datetime.datetime | datetime.date] = None
    station: Optional[str] = Field(default=None, pattern=r"^[A-Z]{4}$")  # 4-letter uppercase code
    region: Optional[str] = Field(default=None, pattern=r"^[A-Z]{3}$")  # 3-letter uppercase code
    monument: Optional[int] = Field(default=None, ge=0, le=9)  # Single digit monument number
    interval: Optional[ProductSampleInterval] = None
    duration: Optional[ProductDuration | Rinex2FileInterval] = None
    satellite_system: Optional[RinexSatelliteSystem] = RinexSatelliteSystem.MIXED  # e.g., "G" for GPS, "R" for GLONASS, etc.
    content: Optional[Rinex3DataType | Rinex2DataType] = Rinex3DataType.OBS  # e.g., "OBS", "NAV", etc.
    filename: Optional[str] = None  # Optional pre-built filename; if not provided, will be built from other fields
    version: RinexVersion = RinexVersion.V3  # Default to RINEX v3; can be overridden to v2 for legacy files
    data_source: Optional[Rinex3DataSource] = Rinex3DataSource.R

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
        
    def build_filename(self) -> str:
        match self.version:
            case RinexVersion.V3 | RinexVersion.V4:
                if not all([self.station, self.monument is not None, self.region, self.duration, self.satellite_system, self.content, self.date]):
                    raise ValueError("Cannot build RINEX v3/v4 filename: missing required fields")
                match self.content:
                    case Rinex3DataType.OBS | Rinex3DataType.MET:
                        filename = f"{self.station}{self.monument}{self.region}_{self.data_source.value}_{self.date.year}{self.date.timetuple().tm_yday:03d}_{self.duration.value}_{self.interval.value}_{self.satellite_system.value}{self.content.value}.rnx"
                    case _:
                        filename = f"{self.station}{self.monument}{self.region}_{self.data_source.value}_{self.date.year}{self.date.timetuple().tm_yday:03d}_{self.duration.value}_{self.satellite_system.value}{self.content.value}.rnx"
            case _:
                if not all([self.station, self.interval, self.content, self.date]):
                    raise ValueError("Cannot build RINEX v2 filename: missing required fields")
                yy = str(self.date.year)[-2:]
                doy = self.date.timetuple().tm_yday
                filename = f"{self.station}{doy:03d}{self.interval.value}.{yy}{self.content.value}"
        return filename
    
    def model_post_init(self, __context):
        if self.filename is None:
            self.filename = self.build_filename()


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
    class Config:
        coerce=True

class RegionConfig(BaseModel):
    region: str
    description: Optional[str] = None

class SatelliteSystemConfig(BaseModel):
    satellite_system: RinexSatelliteSystem
    description: Optional[str] = None

class RinexConfig(BaseModel):
    id: str
    content: Rinex3DataType | Rinex2DataType
    version: Optional[RinexVersion] = RinexVersion.V3
    available: bool = True
    description: Optional[str] = None
    station_set: List[StationConfig]
    monument_set: List[MonumentConfig]
    receiver_set: List[ReceiverConfig]
    region_set: List[RegionConfig]
    sampling_set: List["SampleIntervalConfig"]
    satellite_system_set: List[SatelliteSystemConfig]
    duration_set: List["DurationConfig"]
    directory: str
    filename: str


from .products import SampleIntervalConfig, DurationConfig  # noqa: E402
RinexConfig.model_rebuild()
