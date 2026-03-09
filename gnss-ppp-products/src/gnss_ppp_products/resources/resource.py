import datetime
from fileinput import filename
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from ..resources.remote.utils import _parse_date, _date_to_gps_week
from .products import SampleInterval, ProductCoverage, ProductQuality, ProductType, Solution,TemporalCoverage


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


class FilenameConfig(BaseModel):
    """Configuration for filename template and regex pattern."""
    template: str
    regex: str

    def build(
            self,
            date: datetime.datetime | datetime.date,
            solution: Optional[Solution] = None,
            interval: Optional[str | SampleInterval] = None,
            quality: Optional[ProductQuality | str] = ProductQuality.FINAL,
            version: Optional[str] = "0",
            coverage: Optional[str | ProductCoverage] = ProductCoverage.D_1,
    ) -> str:
        year, doy = _parse_date(date)
        yy = str(year)[-2:]
        gps_week = _date_to_gps_week(date)
        
        # Extract month/day for templates that need them
        if isinstance(date, datetime.datetime):
            month = date.month
            day = date.day
            dow = date.weekday()
        else:
            month = date.month
            day = date.day
            dow = date.weekday()

        if isinstance(interval, str):
            try:
                interval = SampleInterval(interval)
            except ValueError:
                raise ValueError(f"Invalid interval value: {interval}")
        if isinstance(quality, str):
            try:
                quality = ProductQuality(quality)
            except ValueError:
                raise ValueError(f"Invalid quality value: {quality}")
        if isinstance(coverage, str):
            try:
                coverage = ProductCoverage(coverage)
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
            interval: Optional[str | SampleInterval] = None,
            quality: Optional[ProductQuality | str] = ProductQuality.FINAL,
            version: Optional[str] = "0",
            coverage: Optional[str | ProductCoverage] = ProductCoverage.D_1,
    ) -> str:
        year, doy = _parse_date(date)
        yy = str(year)[-2:]

        if isinstance(interval, str):
            try:
                interval = SampleInterval(interval)
            except ValueError:
                raise ValueError(f"Invalid interval value: {interval}")
        if isinstance(quality, str):
            try:
                quality = ProductQuality(quality)
            except ValueError:
                raise ValueError(f"Invalid quality value: {quality}")
        if isinstance(coverage, str):
            try:
                coverage = ProductCoverage(coverage)
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
    intervals: Optional[List[SampleInterval]] = None
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
            sample_interval: Optional[SampleInterval] = None,
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