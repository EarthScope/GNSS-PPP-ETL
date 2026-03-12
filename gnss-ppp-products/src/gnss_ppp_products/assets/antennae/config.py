import datetime
from typing import List, Optional

from .base import AntennaeBase
from .query import AntennaeCalibrationQuery
from ..base.config import CampaignConfig


class AntennaeConfig(AntennaeBase):
    """Configuration for an antennae calibration product."""
    available: bool = True
    description: Optional[str] = None
    notes: Optional[str] = None
    server_id: str
    campaign_set: List[CampaignConfig]

    def build(self,date: datetime.date | datetime.datetime) -> List[AntennaeCalibrationQuery]:
        assert self.directory is not None, "AntennaeConfig must have a directory template to build queries"
        assert self.filename is not None, "AntennaeConfig must have a filename template to build queries"



        default_query = AntennaeCalibrationQuery(
            date=date)
        default_query.build_directory(self.directory)
        default_query.build_filename(self.filename)
        queries: List[AntennaeCalibrationQuery] = [default_query]
        for campaign_info in self.campaign_set:
            query = default_query.model_copy(update={
                "center": campaign_info.center,
                "campaign": campaign_info.campaign,
                "format": self.format,
                "content": self.content,
            })
            query.build_directory(self.directory)
            query.build_filename(self.filename)
            queries.append(query)
        return list(set(queries))