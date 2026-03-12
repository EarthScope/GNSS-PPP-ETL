"""
IGS product filename queries and YAML configuration schemas.
"""

import datetime
from typing import List, Optional

from pydantic import  Field, field_serializer, field_validator
from .base import BaseConfig
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
# Regex fallback patterns for IGS long-form filename placeholders.
# When a field value is not provided, the corresponding pattern is
# substituted into the template so the result can be used as a regex.
# ---------------------------------------------------------------------------

_PRODUCT_PLACEHOLDER_REGEX: dict[str, str] = {
    "center":    r"[A-Z]{3}",
    "version":   r"\d",
    "campaign":  r"[A-Z]{3}",
    "quality":   r"[A-Z]{3}",
    "year":      r"\d{4}",
    "doy":       r"\d{3}",
    "duration":  r"\d{2}[SMHD]",
    "interval":  r"\d{2}[SMHD]",
    "content":   r"[A-Z]{3}",
    "format":    r"[A-Z]{3,4}",
    "gps_week":  r"\d{4}",
    "yy":        r"\d{2}",
    "month":     r"\d{2}",
    "day":       r"\d{2}",
}


class _RegexFallbackDict(dict):
    """Dict that returns regex patterns for unknown placeholder keys."""

    def __missing__(self, key: str) -> str:
        return _PRODUCT_PLACEHOLDER_REGEX.get(key, ".+")


# ---------------------------------------------------------------------------
# Product filename query
# ---------------------------------------------------------------------------


class ProductFileQuery(BaseConfig):
    date: Optional[datetime.datetime | datetime.date] = None
    server: Optional[Server] = None
    center: Optional[str] = None
    version: Optional[str] = "0"
    campaign: Optional[ProductCampaignSpec] = None
    interval: Optional[ProductSampleInterval] = None
    duration: Optional[ProductDuration] = None
    content: Optional[ProductContentType] = None
    format: Optional[ProductFileFormat] = None
    quality: Optional[str] = None  # Solution quality code (FIN, RAP, ULR, …)
    filename: Optional[str] = None
    directory: Optional[str] = None

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
    def from_filename(cls, filename: str) -> "ProductFileQuery":
        center_solution, yeardoy, coverage, sample, content = filename.split("_")

        center = center_solution[:3]
        version = center_solution[3]
        campaign = ProductCampaignSpec(center_solution[4:7])
        quality = center_solution[7:]
        year = int(yeardoy[:4])
        doy = int(yeardoy[4:7])
        hour = int(yeardoy[7:9])
        minute = int(yeardoy[9:11])
        date = datetime.datetime(year, 1, 1) + datetime.timedelta(days=doy - 1, hours=hour, minutes=minute)
        duration = ProductDuration(coverage)
        interval = ProductSampleInterval(sample)
        content_type = ProductContentType(content.split(".")[0])
        file_format = ProductFileFormat(content.split(".")[1].split(".")[0])
        return cls(
            date=date,
            center=center,
            version=version,
            campaign=campaign,
            interval=interval,
            duration=duration,
            content=content_type,
            format=file_format,
            quality=quality,
            filename=filename,
        )

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
        if self.center is not None:
            subs["center"] = self.center
        if self.version is not None:
            subs["version"] = self.version
        if self.campaign is not None:
            subs["campaign"] = self.campaign.value
        if self.quality is not None:
            subs["quality"] = self.quality if isinstance(self.quality, str) else self.quality.value
        if self.interval is not None:
            subs["interval"] = self.interval.value
        if self.duration is not None:
            subs["duration"] = self.duration.value
        if self.content is not None:
            subs["content"] = self.content.value
        if self.format is not None:
            subs["format"] = self.format.value
        return subs

    def build_filename(self, template: str) -> str:
        """
        Build a filename pattern from a template string.

        Known field values are substituted literally; missing fields
        become regex patterns suitable for matching against directory
        listings.

        Parameters
        ----------
        template : str
            Filename template with ``{placeholder}`` tokens, e.g.
            ``"{center}{version}{campaign}{quality}_{year}{doy}0000_{duration}_{interval}_ORB.SP3.*"``

        Returns
        -------
        str
            Pattern string with all placeholders resolved.
        """
        self.filename = template.format_map(_RegexFallbackDict(self._substitution_map()))

    def build_directory(self, template: str) -> str:
        """Build a directory path from a template, substituting known values."""
        self.directory = template.format_map(_RegexFallbackDict(self._substitution_map()))


# ---------------------------------------------------------------------------
# YAML product configuration schemas
# ---------------------------------------------------------------------------


class QualityConfig(BaseConfig):
    quality: ProductQuality
    description: Optional[str] = None

class SampleIntervalConfig(BaseConfig):
    interval: ProductSampleInterval
    description: Optional[str] = None

class DurationConfig(BaseConfig):
    duration: ProductDuration | Rinex2FileInterval
    description: Optional[str] = None

class CampaignConfig(BaseConfig):
    center: AnalysisCenter
    campaign: ProductCampaignSpec
    description: Optional[str] = None

class ProductConfig(BaseConfig):
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

    def build(self, date: datetime.datetime | datetime.date) -> List[ProductFileQuery]:
        """Expand config into all combinations of quality/campaign/sampling/duration."""
        queries: list[ProductFileQuery] = []
        quality_set = [q.quality.value for q in self.quality_set] or [None]
        campaign_set = self.campaign_set or [None]
        sampling_set = [s.interval for s in self.sampling_set] or [None]
        duration_set = [d.duration for d in self.duration_set] or [None]
        for quality in quality_set:
            for campaign in campaign_set:
                for sampling in sampling_set:
                    for duration in duration_set:
                        query = ProductFileQuery(
                            date=date,
                            center=campaign.center.value if campaign else None,
                            version=self.version,
                            campaign=campaign.campaign if campaign else None,
                            quality=quality,
                            interval=sampling,
                            duration=duration,
                            content=self.content,
                            format=self.format,
                        )
                        query.build_filename(self.filename)
                        query.build_directory(self.directory)
                        queries.append(query)
        return queries

class RemoteProductAddress(BaseConfig):
    server: Server
    directory: str
    filename: str
    file_id: str  # Which file config was used
    type: ProductType
    quality: ProductQuality
    solution: Optional[Solution] = None
