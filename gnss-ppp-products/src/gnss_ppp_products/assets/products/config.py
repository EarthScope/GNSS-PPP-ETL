from pydantic import BaseModel
from typing import List, Optional
import datetime

from .base import (
    ProductBase,
    ProductSolutionType,
)

from .query import ProductFileQuery
from ..base.config import CampaignConfig, SampleIntervalConfig, DurationConfig

# ---------------------------------------------------------------------------
# YAML product configuration schemas
# ---------------------------------------------------------------------------


class QualityConfig(BaseModel):
    quality: ProductSolutionType
    description: Optional[str] = None


class ProductConfig(ProductBase):
    """Configuration for a GNSS product with the new files structure."""
    id: str
    server_id: str
    available: bool = True
    description: Optional[str] = None
    quality_set: List[QualityConfig]
    campaign_set: List[CampaignConfig]
    sampling_set: List[SampleIntervalConfig]
    duration_set: List[DurationConfig]
    notes: Optional[str] = None

    def build(self, date: datetime.datetime | datetime.date) -> List[ProductFileQuery]:
        """Expand config into all combinations of quality/campaign/sampling/duration."""
        assert self.filename is not None, "ProductConfig must have a filename template to build queries"
        assert self.directory is not None, "ProductConfig must have a directory template to build queries"

        queries: list[ProductFileQuery] = []
        quality_set = [q.quality for q in self.quality_set] or [None]
        campaign_set = self.campaign_set or [None]
        sampling_set = [s.interval for s in self.sampling_set] or [None]
        duration_set = [d.duration for d in self.duration_set] or [None]
        for quality in quality_set:
            for campaign in campaign_set:
                for sampling in sampling_set:
                    for duration in duration_set:
                        query = ProductFileQuery(
                            date=date,
                            center=campaign.center if campaign else None,
                            version=self.version,
                            campaign=campaign.campaign if campaign else None,
                            solution=quality,
                            interval=sampling,
                            duration=duration,
                            content=self.content,
                            format=self.format,
                        )
                        query.build_filename(self.filename)
                        query.build_directory(self.directory)
                        queries.append(query)
        return queries