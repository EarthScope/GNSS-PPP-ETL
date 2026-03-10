"""
IGS product filename queries and YAML configuration schemas.
"""

import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from ..remote.utils import _parse_date, _date_to_gps_week
from ..products import Solution, ProductQuality, TemporalCoverage
from ..igs_conventions import (
    AnalysisCenter,
    ProductCampaignSpec,
    ProductSolutionType,
    ProductSampleInterval,
    ProductDuration,
    ProductType,
    ProductFileFormat,
    ProductContentType,
    Rinex2FileInterval,
)
from .server import Server


# ---------------------------------------------------------------------------
# Product filename query
# ---------------------------------------------------------------------------


class ProductFileQuery(BaseModel):
    date: Optional[datetime.datetime | datetime.date] = None
    center: Optional[str] = Field(default=None, pattern=r"^[A-Z]{3}$")  # 3-letter uppercase code
    version: Optional[str] = Field(default="0", pattern=r"^\d+$")  # Version number, default "0"
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


# ---------------------------------------------------------------------------
# YAML product configuration schemas
# ---------------------------------------------------------------------------


class QualityConfig(BaseModel):
    quality: ProductQuality
    description: Optional[str] = None

class SampleIntervalConfig(BaseModel):
    interval: ProductSampleInterval
    description: Optional[str] = None

class DurationConfig(BaseModel):
    duration: ProductDuration | Rinex2FileInterval
    description: Optional[str] = None

class CampaignConfig(BaseModel):
    center: AnalysisCenter
    campaign: ProductCampaignSpec
    description: Optional[str] = None

class ProductConfig(BaseModel):
    """Configuration for a GNSS product with the new files structure."""
    id: str
    version: str
    filename: str
    directory: str
    format: ProductFileFormat
    content: ProductContentType
    server_id: str
    available: bool = True
    description: Optional[str] = None
    quality_set: List[QualityConfig]
    campaign_set: List[CampaignConfig]
    sampling_set: List[SampleIntervalConfig]
    duration_set: List[DurationConfig]
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
