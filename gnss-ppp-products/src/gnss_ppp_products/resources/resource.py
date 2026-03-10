import datetime
from fileinput import filename
from enum import Enum
import re
from typing import List, Optional

from pydantic import BaseModel, Field

from ..resources.remote.utils import _parse_date, _date_to_gps_week
from .products import SampleInterval, ProductDuration, ProductQuality, Solution,TemporalCoverage

from .igs_conventions import (
    ProductCampaignSpec,
    ProductSolutionType,
    ProductSampleInterval,
    ProductDuration,
    ProductType,
    ProductFileFormat,
    ProductContentType,
    Rinex3DataType,
    RinexSatelliteSystem,
    Rinex3DataSource,
    Rinex2DataType,
    Rinex2FileInterval,
    RinexVersion,
    )

class TimeIndex(str, Enum):
    """Available time index placeholders for file paths."""
    YEAR = "YEAR"
    DOY = "DOY"
    GPS_WEEK = "GPS_WEEK"
    MONTH = "MONTH"
    DAY = "DAY"
    YY = "YY"
    DOW = "DOW"


class ServerProtocol(str, Enum):
    FTP = "ftp"
    FTPS = "ftps"  # FTP over TLS (e.g., CDDIS)
    HTTP = "http"
    HTTPS = "https"


class Server(BaseModel):
    id: str
    name: str
    protocol: ServerProtocol
    hostname: str
    auth_required: bool = False
    notes: Optional[str] = None

class ProductFileQuery(BaseModel):
    date: Optional[datetime.datetime | datetime.date] = None
    center: Optional[str] = Field(default=None, regex=r"^[A-Z]{3}$")  # 3-letter uppercase code
    version: Optional[str] = Field(default="0", regex=r"^\d+$")  # Version number, default "0"
    campaign: Optional[ProductCampaignSpec] = None
    interval: Optional[ProductSampleInterval] = None
    duration: Optional[ProductDuration] = None
    content: Optional[ProductContentType] = None
    format: Optional[ProductFileFormat] = None
    solution: Optional[ProductSolutionType] = None  
    filename: Optional[str] = None  # Optional pre-built filename; if not provided, will be built from other fields

    @classmethod
    def from_filename(cls, filename: str) -> "ProductFileQuery":
        center_solution,yeardoy,coverage,sample,content = filename.split("_")

        center = center_solution[:3]
        version = center_solution[3]
        campaign = ProductCampaignSpec(center_solution[4:7])
        solution = ProductSolutionType(center_solution[7:])
        year = int(yeardoy[:4])
        doy = int(yeardoy[4:7])
        hour = int(yeardoy[7:9])
        minute = int(yeardoy[9:11])
        date = datetime.datetime(year, 1, 1) + datetime.timedelta(days=doy-1, hours=hour, minutes=minute)
        duration = ProductDuration(coverage)
        interval = ProductSampleInterval(sample)
        content_type = ProductContentType(content.split(".")[0]) # Remove file extension
        file_format = ProductFileFormat(content.split(".")[1].split(".")[0]) # Extract format before any additional extensions
        return cls(
            date=date,
            center=center,
            version=version,
            campaign= campaign,
            interval=interval,
            duration=duration,
            content=content_type,
            format=file_format,
            solution=solution,
            filename=filename
        )
    def build_filename(self) -> str:
        if not all([self.center, self.version, self.campaign, self.solution, self.date, self.duration, self.interval, self.content, self.format]):
            raise ValueError("Cannot build filename: missing required fields")
        year, doy = _parse_date(self.date)
        filename = f"{self.center}{self.version}{self.campaign.value}{self.solution.value}_{year}{doy:03d}_{self.duration.value}_{self.interval.value}_{self.content.value}.{self.format.value}"
        return filename
    
    def model_post_init(self, __context):
        if self.filename is None:
            self.filename = self.build_filename()

class RinexFileQuery(BaseModel):
    date: Optional[datetime.datetime | datetime.date] = None
    station: Optional[str] = Field(default=None, regex=r"^[A-Z]{4}$")  # 4-letter uppercase code
    region: Optional[str] = Field(default=None, regex=r"^[A-Z]{3}$")  # 3-letter uppercase code
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
        # Example RINEX 3 filename: "ABCD1234_2025001_00M_01D_GN.rnx"
        # Detect if we are parsing an observation/meteorological file or a navigation file based on the presence of the "FRU" field
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

        data_source = data_source[0]  # First character indicates data source (e.g., "S" for stream, "R" for receiver)

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
        # determine if this is a RINEX v3/v4 filename or a RINEX v2 filename based on the presence of certain patterns
        if len(filename.split("_")) > 2:
            # Likely a RINEX v3/v4 filename
            return cls._from_filename_v3_v4(filename)
        else:
            # Likely a RINEX v2 filename
            return cls._from_filename_v2(filename)
        
    def build_filename(self) -> str:
        match self.version:
            case RinexVersion.V3 | RinexVersion.V4:
                if not all([self.station, self.monument is not None, self.region, self.duration, self.satellite_system, self.content, self.date]):
                    raise ValueError("Cannot build RINEX v3/v4 filename: missing required fields")
                # Build filename according to RINEX v3/v4 conventions
                match self.content:
                    case Rinex3DataType.OBS | Rinex3DataType.MET:
                        filename = f"{self.station}{self.monument}{self.region}_{self.data_source.value}_{self.date.year}{self.date.timetuple().tm_yday:03d}_{self.duration.value}_{self.interval.value}_{self.satellite_system.value}{self.content.value}.rnx"

                    case _:
                        filename = f"{self.station}{self.monument}{self.region}_{self.data_source.value}_{self.date.year}{self.date.timetuple().tm_yday:03d}_{self.duration.value}_{self.satellite_system.value}{self.content.value}.rnx"
            case _:
                if not all([self.station, self.interval, self.content, self.date]):
                    raise ValueError("Cannot build RINEX v2 filename: missing required fields")
                # Build filename according to RINEX v2 conventions
                yy = str(self.date.year)[-2:]
                doy = self.date.timetuple().tm_yday
                filename = f"{self.station}{doy:03d}{self.interval.value}.{yy}{self.content.value}"
        return filename
    
    def model_post_init(self, __context):
        if self.filename is None:
            self.filename = self.build_filename()

class FilenameConfig(BaseModel):
    """Configuration for filename template and regex pattern."""
    template: str
    regex: str

    # "{center}{version}{campaign}{quality}_{year}{doy}0000_{coverage}_01D_ERP.ERP.gz"
    def build(
            self,
            date: datetime.datetime | datetime.date,
            center: Optional[str] = None,
            campaign: Optional[str] = None,
            interval: Optional[str | ProductSampleInterval] = None,
            quality: Optional[ProductQuality | str] = ProductQuality.FINAL,
            version: Optional[str] = "0",
            duration: Optional[str | ProductDuration] = ProductDuration.D_1,
    ) -> str:
        year, doy = _parse_date(date)
        yy = str(year)[-2:]
        gps_week = _date_to_gps_week(date)
        
  
        if isinstance(interval, str):
            try:
                interval = ProductSampleInterval(interval)
            except ValueError:
                raise ValueError(f"Invalid interval value: {interval}")
        if isinstance(quality, str):
            try:
                quality = ProductQuality(quality)
            except ValueError:
                raise ValueError(f"Invalid quality value: {quality}")
        if isinstance(coverage, str):
            try:
                coverage = ProductDuration(coverage)
            except ValueError:
                raise ValueError(f"Invalid coverage value: {coverage}")
        
        if center is None:
            center = r"([A-Z]{3})"  # Match any 3-letter center code if not provided
        if campaign is None:
            campaign = r"([A-Z]{3})"  # Optional campaign code
        if quality is None:
            quality = "|".join(re.escape(q.value) for q in ProductQuality)  # Match any quality if not provided
            quality = rf"({quality})"
        if interval is None:
            interval = "|".join(re.escape(i.value) for i in ProductSampleInterval)  # Match any interval if not provided
            interval = rf"({interval})"

        if solution is not None and interval is not None:
            filename = self.template.format(
                solution_prefix=solution.prefix,
                version=version,
                solution_code=solution.code,
                qual=quality.value,
                year=year,
                doy=doy,
                gps_week=gps_week,
                yy=yy,
                month=month,
                day=day,
                dow=dow,
                coverage=coverage.value,
                interval=interval.value if interval else None
            )
        else:
            filename = self.regex.format(
                solution_prefix=solution.prefix if solution else None,
                qual=quality.value,
                year=year,
                doy=doy,
                gps_week=gps_week,
                yy=yy,
                month=month,
                day=day,
                dow=dow,
                coverage=coverage.value,
                interval=interval.value if interval else None,
            )
        return filename

class ProductQuery
class FileConfig(BaseModel):
    """
    Configuration for a single file location.
    
    Replaces the separate directory/filename fields with a unified
    file configuration that can represent multiple file variants
    (e.g., current vs archive, different date-based formats).
    """
    id: str
    timeindices: List[TimeIndex] = Field(default_factory=list)
    directory: str
    filename: FilenameConfig
    valid_from: Optional[str] = None  # ISO date string
    valid_to: Optional[str] = None    # ISO date string

    def build_directory(self, date: datetime.datetime | datetime.date) -> str:
        """Build the directory path with date placeholders filled in."""
        year, doy = _parse_date(date)
        yy = str(year)[-2:]
        gps_week = _date_to_gps_week(date)
        
        # Extract month/day if date is datetime
        if isinstance(date, datetime.datetime):
            month = f"{date.month:02d}"
            day = f"{date.day:02d}"
            dow = str(date.weekday())  # 0=Monday in Python
        else:
            month = f"{date.month:02d}"
            day = f"{date.day:02d}"
            dow = str(date.weekday())
        
        directory = self.directory.format(
            year=year,
            doy=doy,
            gps_week=gps_week,
            yy=yy,
            month=month,
            day=day,
            dow=dow
        )
        return directory

    def is_valid_for_date(self, date: datetime.datetime | datetime.date) -> bool:
        """Check if this file config is valid for the given date."""
        if isinstance(date, datetime.datetime):
            date = date.date()
        
        if self.valid_from:
            valid_from = datetime.date.fromisoformat(self.valid_from)
            if date < valid_from:
                return False
        
        if self.valid_to:
            valid_to = datetime.date.fromisoformat(self.valid_to)
            if date > valid_to:
                return False
        
        return True


# Keep legacy classes for backward compatibility during migration
class Directory(BaseModel):
    pattern: str

    def build(self, date: datetime.datetime | datetime.date) -> str:
        year, doy = _parse_date(date)
        yy = str(year)[-2:]
        gps_week = _date_to_gps_week(date)
        directory = self.pattern.format(year=year, doy=doy, gps_week=gps_week, yy=yy)
        return directory


class Filename(BaseModel):
    template: str
    regex: str

    def build(
            self,
            date: datetime.datetime | datetime.date,
            solution: Optional[Solution] = None,
            interval: Optional[str | ProductSampleInterval] = None,
            quality: Optional[ProductQuality | str] = ProductQuality.FINAL,
            version: Optional[str] = "0",
            coverage: Optional[str | ProductDuration] = ProductDuration.D_1,
    ) -> str:
        year, doy = _parse_date(date)
        yy = str(year)[-2:]

        if isinstance(interval, str):
            try:
                interval = ProductSampleInterval(interval)
            except ValueError:
                raise ValueError(f"Invalid interval value: {interval}")
        if isinstance(quality, str):
            try:
                quality = ProductQuality(quality)
            except ValueError:
                raise ValueError(f"Invalid quality value: {quality}")
        if isinstance(coverage, str):
            try:
                coverage = ProductDuration(coverage)
            except ValueError:
                raise ValueError(f"Invalid coverage value: {coverage}")

        if solution is not None and interval is not None:
            filename = self.template.format(
                solution_prefix=solution.prefix,
                version=version,
                solution_code=solution.code,
                qual=quality.value,
                year=year,
                doy=doy,
                coverage=coverage.value,
                interval=interval.value if interval else None
            )
        else:
            filename = self.regex.format(
                qual=quality.value,
                year=year,
                doy=doy,
                coverage=coverage.value,
                interval=interval.value if interval else None,
                yy=yy
            )
        return filename


class ProductConfig(BaseModel):
    """Configuration for a GNSS product with the new files structure."""
    id: str
    type: ProductType
    server_id: str
    available: bool = True
    description: Optional[str] = None
    qualities: List[ProductQuality]
    solutions: List[Solution]
    files: List[FileConfig]
    intervals: Optional[List[ProductSampleInterval]] = None
    extensions: Optional[List[str]] = None
    notes: Optional[str] = None


class RemoteProductAddress(BaseModel):
    server: Server
    directory: str
    filename: str
    file_id: str  # Which file config was used
    type: ProductType
    quality: ProductQuality
    solution: Optional[Solution] = None


class GNSSCenterConfig(BaseModel):
    """Configuration for a GNSS product center."""
    name: str
    code: str
    description: Optional[str] = None
    website: Optional[str] = None
    servers: List[Server]
    products: List[ProductConfig]

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "GNSSCenterConfig":
        import yaml
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)
        return cls(**data)

    def list_products(
            self,
            date: datetime.datetime | datetime.date,
            product_type: Optional[ProductType] = None,
            product_quality: Optional[ProductQuality] = None,
            sample_interval: Optional[ProductSampleInterval] = None,
            temporal_coverage: Optional[TemporalCoverage] = None,
            file_id: Optional[str] = None
    ) -> List[RemoteProductAddress]:
        """
        Get product addresses matching the specified criteria.
        
        Parameters
        ----------
        date : datetime.datetime | datetime.date
            The date to query products for
        file_id : str, optional
            Specific file ID to filter (e.g., "current", "archive")
        product_type : ProductType, optional
            Specific product type to filter
        product_quality : ProductQuality, optional
            Specific product quality to filter
        sample_interval : SampleInterval, optional
            Specific sample interval to filter
        temporal_coverage : TemporalCoverage, optional
            Specific temporal coverage to filter
        """
        product_addresses: list[RemoteProductAddress] = []
        for product in self.products:
            if not product.available:
                continue
                
            server = next((s for s in self.servers if s.id == product.server_id), None)
            if server is None:
                raise ValueError(f"Product {product.type} references unknown server_id {product.server_id}")
            
            # Filter files by file_id if specified
            files_to_use = product.files
            if file_id:
                files_to_use = [f for f in product.files if f.id == file_id]
            
            # Filter files by date validity
            files_to_use = [f for f in files_to_use if f.is_valid_for_date(date)]
            
            # Build each combination of quality/solution/intervals/files
            qualities = [x for x in product.qualities if not product_quality or x == product_quality] or [None]
            solutions = product.solutions or [None]
 
            for file_config in files_to_use:
                for quality in qualities:
                    for solution in solutions:
            
                        filename = file_config.filename.build(
                            date=date,
                            solution=solution,
                            quality=quality
                            
                        )
                        directory = file_config.build_directory(date)

                        address = RemoteProductAddress(
                            server=server,
                            directory=directory,
                            filename=filename,
                            file_id=file_config.id,
                            type=product.type,
                            quality=quality,
                            solution=solution
                        )
                        product_addresses.append(address)

        return product_addresses