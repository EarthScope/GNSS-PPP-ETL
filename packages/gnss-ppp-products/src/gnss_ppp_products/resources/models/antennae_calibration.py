from typing import List, Optional
from enum import Enum
import datetime
import re

from gnss_ppp_products.resources.remote.utils import _date_to_gps_week, _parse_date
from .server import Server

from .base import BaseConfig
from ..types import (
    AnalysisCenter,
    ProductCampaignSpec,
    ProductFileFormat,
    ProductContentType,
    RinexVersion,
)

_ANTENNAE_PLACEHOLDER_REGEX: dict[str, str] = {
    "gps_week":  r"\d{4}",
    "reference_frame": r"(5|8|14|20|R3)",
    "center": r"[a-z]{3}",
}

class _RegexFallbackDict(dict):
    """Dict that returns regex patterns for unknown placeholder keys."""

    def __missing__(self, key: str) -> str:
        return _ANTENNAE_PLACEHOLDER_REGEX.get(key, ".+")

class IGSAntexReferenceFrameType(str, Enum):
    """Reference frame types for ANTEX files."""
    IGS05 = "5"
    IGS08 = "8"
    IGS14 = "14"
    IGS20 = "20"
    IGSR3 = "R3"


def determine_frame(
    date: datetime.date | datetime.datetime,
) -> IGSAntexReferenceFrameType:
    """Determine the appropriate IGS frame based on date."""
    if isinstance(date, datetime.datetime):
        date = date.date()

    if date >= datetime.date(2022, 11, 27):
        return IGSAntexReferenceFrameType.IGS20
    elif date >= datetime.date(2017, 1, 29):
        return IGSAntexReferenceFrameType.IGS14
    elif date >= datetime.date(2011,4,17):
        return IGSAntexReferenceFrameType.IGS08
    elif date >= datetime.date(2006, 11, 5):
        return IGSAntexReferenceFrameType.IGS05  # Assuming a placeholder for the earliest frame
    else:
        raise ValueError(f"No suitable IGS frame found for date {date}")
    

class AntennaeCalibrationQuery(BaseConfig):
    date: datetime.date | datetime.datetime
    center: Optional[str] = "IGS"
    campaign: Optional[str] = "STATIC"
    format: ProductFileFormat = ProductFileFormat.ATX
    content: ProductContentType = ProductContentType.ATT
    server: Optional[Server] = None
    directory: Optional[str] = None
    filename: Optional[str] = None

    def _substitution_map(self) -> dict[str, str]:
        """Collect known field values as a ``{placeholder: value}`` mapping."""
        subs: dict[str, str] = {}
        if self.date is not None:
            subs["reference_frame"] = determine_frame(self.date).value

        if self.center is not None:
            subs["center"] = self.center.lower()
        
        return subs

    @classmethod
    def from_filename(cls, filename: str) -> "AntennaeCalibrationQuery":
        center: str = filename[:3]
        date = None
        if len(filename.split("_")) == 2:
            # This is likely an antex file with a gps_week
            gps_week = int(re.search(r"\d{4}", filename).group(0))
            date = datetime.date(1980, 1, 6) + datetime.timedelta(weeks=gps_week)
        return cls(
            date=date,
            center=center,
            filename=filename,
            format =ProductFileFormat.ATX,
            content = ProductContentType.ATT,
        )
    
    def load_date_from_filename(self) -> None:
        if self.filename and len(self.filename.split("_")) == 2:
            gps_week = int(re.search(r"\d{4}", self.filename).group(0))
            self.date = (datetime.datetime(1980, 1, 6) + datetime.timedelta(weeks=gps_week)).astimezone(datetime.timezone.utc)

    def build_filename(self,template: str) -> str:
        subs = _RegexFallbackDict(self._substitution_map())

        self.filename = template.format_map(subs)

    def build_directory(self,template: str) -> str:
        subs = _RegexFallbackDict(self._substitution_map())
        self.directory = template.format_map(subs)

class AntennaeCalibrationConfig(BaseConfig):
    """Configuration for antennae calibration products."""
    available: bool = True
    description: Optional[str] = None
    server_id: str
    format: ProductFileFormat = ProductFileFormat.ATX
    content: ProductContentType = ProductContentType.ATT
    directory: Optional[str] = None
    filename: Optional[str] = None
    notes: Optional[str] = None
    campaign_set: list[dict[str, str]] = [{"campaign": "STATIC", "center": "IGS"}]

    def build(self,date: datetime.date | datetime.datetime) -> List[AntennaeCalibrationQuery]:
        queries: List[AntennaeCalibrationQuery] = []
        for campaign_info in self.campaign_set:
            query = AntennaeCalibrationQuery(
                date=date,
                center=campaign_info.get("center", None),
                campaign=campaign_info.get("campaign", None),
                format=self.format,
                content=self.content,
               
            )
            query.build_directory(self.directory)
            query.build_filename(self.filename)
            queries.append(query)
        return queries