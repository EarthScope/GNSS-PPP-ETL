import datetime
from typing import Optional
import re


from ..server import Server
from .base import (
    ProductCampaignSpec,
    AntennaeBase,
    _RegexFallbackDict,
    AnalysisCenter)
from .utils import determine_frame,gps_week_to_date

class AntennaeCalibrationQuery(AntennaeBase):
    campaign: Optional[ProductCampaignSpec] = ProductCampaignSpec.STATIC
    server: Optional[Server] = None
    center: Optional[AnalysisCenter] = AnalysisCenter.IGS 
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
        center: str = AnalysisCenter(filename[:3])
        date = cls._date_from_filename(filename)

        return cls(
            date=date,
            center=center,
            filename=filename,
        )
    
    @staticmethod
    def _date_from_filename(filename:str) -> Optional[datetime.datetime]:
        if len(filename.split("_")) == 2:
            gps_week_search: Optional[re.Match] = re.search(r"\d{4}", filename)
            if gps_week_search:
                gps_week = int(gps_week_search.group(0))
                return gps_week_to_date(gps_week)

    def load_date_from_filename(self) -> None:
        if self.filename:
            date = self._date_from_filename(self.filename)
            if date:
                self.date = date

    def build_filename(self,template: str) -> None:
        subs = _RegexFallbackDict(self._substitution_map())

        self.filename = template.format_map(subs)

    def build_directory(self,template: str) -> None:
        subs = _RegexFallbackDict(self._substitution_map())
        self.directory = template.format_map(subs)
