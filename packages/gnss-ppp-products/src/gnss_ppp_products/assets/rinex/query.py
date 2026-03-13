import datetime
from typing import Optional

from ..utils import parse_date, date_to_gps_week
from ..server import Server
from ..base.igs_conventions import (
    ProductSampleInterval,
    ProductDuration,
    Rinex3DataType,
    Rinex3DataSource,
    Rinex2DataType,
    Rinex2FileInterval,
    RinexSatelliteSystem,
    RinexVersion,
)
from .base import RinexBase, _RegexFallbackDict


class RinexFileQuery(RinexBase):
    server: Optional[Server] = None

    @classmethod
    def _from_filename_v3_v4(cls, filename: str) -> "RinexFileQuery":
        """
        Parse a RINEX v3/v4 filename.

        Observation and Meteorological Files:
            SSSSMRCCC_S_YYYYDDDHHMM_DDU_FRU_DT.fff.cmp

        Navigation Files:
            SSSSMRCCC_S_YYYYDDDHHMM_DDU_DT.fff.cmp
        """
        segments = filename.split("_")
        if len(segments) == 5:
            # Navigation file format
            station_region, data_source, yeardoy, coverage, satellite_system_ext = segments
            content_type = Rinex3DataType.NAV
        elif len(segments) == 6:
            # Observation or meteorological file format
            station_region, data_source, yeardoy, coverage, interval, satellite_system_ext = segments
            content_type = Rinex3DataType.OBS if "O" in satellite_system_ext else Rinex3DataType.MET
        else:
            raise ValueError(f"Filename '{filename}' does not match expected RINEX formats")

        station = station_region[:4]
        monument = station_region[4]
        receiver = station_region[5]
        region = station_region[6:]

        data_source = data_source[0]

        year = int(yeardoy[:4])
        doy = int(yeardoy[4:7])
        hour = int(yeardoy[7:9])
        minute = int(yeardoy[9:11])
        date = datetime.datetime(year, 1, 1) + datetime.timedelta(days=doy - 1, hours=hour, minutes=minute)

        coverage = ProductDuration(coverage)
        if content_type != Rinex3DataType.NAV:
            interval = ProductSampleInterval(interval)
        else:
            interval = None

        satellite_system = RinexSatelliteSystem(satellite_system_ext[0])
        content_type = Rinex3DataType(satellite_system_ext[1:])
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
            version=RinexVersion.V3,
        )

    @classmethod
    def _from_filename_v2(cls, filename: str) -> "RinexFileQuery":
        """
        Parse a RINEX v2 filename.

        Format: ssssdddf.yyt
        """
        name, ext = filename.split(".")
        station = name[:4]
        doy = name[4:7]
        file_seq = Rinex2FileInterval(name[7:])
        yy = name[-2:]
        v2_type = Rinex2DataType(name[-1])
        date = datetime.datetime(
            year=int("20" + yy),
            month=1,
            day=1,
        ) + datetime.timedelta(days=int(doy) - 1)
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
            interval=file_seq,
            content=v2_type,
            version=RinexVersion.V2,
            filename=filename,
            satellite_system=satellite_system,
        )

    @classmethod
    def from_filename(cls, filename: str) -> "RinexFileQuery":
        if len(filename.split("_")) > 2:
            return cls._from_filename_v3_v4(filename)
        else:
            return cls._from_filename_v2(filename)

    # -- substitution helpers ------------------------------------------------

    def _substitution_map(self) -> dict[str, str]:
        """Collect known field values as a ``{placeholder: value}`` mapping."""
        subs: dict[str, str] = {}
        if self.date is not None:
            year, doy = parse_date(self.date)
            subs["year"] = year
            subs["doy"] = doy
            subs["gps_week"] = str(date_to_gps_week(self.date))
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

    def build_filename(self, template: str) -> None:
        self.filename = template.format_map(_RegexFallbackDict(self._substitution_map()))

    def build_directory(self, template: str) -> None:
        self.directory = template.format_map(_RegexFallbackDict(self._substitution_map()))
