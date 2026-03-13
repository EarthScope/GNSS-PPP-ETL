import datetime
from typing import Optional

from .config import BaseConfig
from .igs_conventions import AnalysisCenter,ProductFileFormat, ProductContentType,ProductCampaignSpec

class AssetBase(BaseConfig):
    """Base class for all asset configurations."""
    date: Optional[datetime.datetime | datetime.date] = None
    center: Optional[AnalysisCenter] = None
    format: Optional[ProductFileFormat] = None
    content: Optional[ProductContentType] = None
    campaign: Optional[ProductCampaignSpec] = None
    filename: Optional[str] = None
    directory: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None