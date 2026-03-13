from pydantic import BaseModel, ConfigDict, field_serializer, field_validator
import datetime
from typing import List, Optional, Union

from .igs_conventions import (
    AnalysisCenter,
    ProductCampaignSpec,
    ProductSampleInterval,
    ProductSolutionType,
    ProductDuration,
    Rinex2FileInterval,
)


class BaseConfig(BaseModel):
    """Base configuration model with common settings."""
    date: Optional[datetime.datetime | datetime.date] = None
    
    model_config = ConfigDict(
        #use_enum_values=True,  # Serialize enums using their values
    )
    @field_serializer("date")
    def _serialize_date(self, date: Optional[datetime.datetime | datetime.date]) -> Optional[str]:
        if date is None:
            return None
        if isinstance(date, datetime.date) and not isinstance(date, datetime.datetime):
            date = datetime.datetime.combine(date, datetime.time(0, 0))
        return date.astimezone(datetime.timezone.utc).isoformat()
    
    @field_validator("date")
    def _validate_date(cls, date: Optional[datetime.datetime | datetime.date]) -> Optional[datetime.datetime | datetime.date]:
        if date is None:
            return None
        if isinstance(date, str):
            return datetime.datetime.fromisoformat(date).astimezone(datetime.timezone.utc)
        if isinstance(date, datetime.date) and not isinstance(date, datetime.datetime):
            return datetime.datetime.combine(date, datetime.time(0, 0))
        return date


# ---------------------------------------------------------------------------
# Shared YAML configuration schemas
# ---------------------------------------------------------------------------


class CampaignConfig(BaseModel):
    center: AnalysisCenter
    campaign: ProductCampaignSpec
    description: Optional[str] = None


class SampleIntervalConfig(BaseModel):
    interval: ProductSampleInterval
    description: Optional[str] = None


class DurationConfig(BaseModel):
    duration: ProductDuration | Rinex2FileInterval
    description: Optional[str] = None
