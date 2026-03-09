import datetime
from fileinput import filename

from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

from ..resources.remote.utils import _parse_date, _date_to_gps_week
from .products import SampleInterval,ProductCoverage,ProductQuality, ProductType,Solution

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
            date:datetime.datetime | datetime.date, 
            solution: Optional[Solution] = None,
            interval:Optional[str | SampleInterval] = None,
            quality: Optional[ProductQuality |str] = ProductQuality.FINAL,
            version: Optional[str] = "0",
            coverage: Optional[str|ProductCoverage] = ProductCoverage.D_1,
            ) -> str:
        year, doy = _parse_date(date)
        yy = str(year)[-2:]

        if isinstance(interval,str):
            try:
                interval = SampleInterval(interval)
            except ValueError:
                raise ValueError(f"Invalid interval value: {interval}")
        if isinstance(quality,str):
            try:    
                quality = ProductQuality(quality)
            except ValueError:
                raise ValueError(f"Invalid quality value: {quality}")
        if isinstance(coverage,str):
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
    type: ProductType
    qualities: List[ProductQuality]  # e.g., ['FIN', 'RAP']
    server_id: str  # e.g., 'wuhan_ftp'
    solutions: List[Solution]  # e.g., [{'code': 'OPS', 'prefix': 'BRD'}]
    directory: Directory
    filename: Filename
    intervals: Optional[List[SampleInterval]] = None  # e.g., ['05M', '15M']
    extensions: List[str]  # e.g., ['.rnx', '.rnx.gz']

class RemoteProductAddress(BaseModel):
    server: Server
    directory: str
    filename: str
    type: str
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
            date: datetime.datetime | datetime.date
    ) -> List[RemoteProductAddress]:
        """Get product addresses matching the specified criteria."""
        product_addresses: list[RemoteProductAddress] = []
        for product in self.products:
            server = next((s for s in self.servers if s.id == product.server_id), None)
            if server is None:
                raise ValueError(f"Product {product.type} references unknown server_id {product.server_id}")
            # build each combination of quality/solution/intervals for the product
            # Use [None] fallback for empty lists so loop executes once with None values
            qualities = product.qualities or [None]
            solutions = product.solutions or [None]
            intervals = product.intervals or [None]
            for quality in qualities:
                for solution in solutions:
                    for interval in intervals:
                        filename = product.filename.build(
                            date=date,
                            solution=solution,
                            interval=interval.value if interval else None,
                            quality=quality
                        )
                        directory = product.directory.build(date)

                        address = RemoteProductAddress(
                            server=server,
                            directory=directory,
                            filename=filename,
                            type=product.type,
                            quality=quality,
                            solution=solution
                        )
                        product_addresses.append(address)

        return product_addresses