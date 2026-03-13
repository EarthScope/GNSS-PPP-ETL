from enum import Enum
from typing import Optional
from ..base import (
    AssetBase,
    AnalysisCenter,
    ProductFileFormat,
    ProductContentType,
    ProductCampaignSpec,
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

class AntennaeBase(AssetBase):
    """Base class for antennae calibration products."""

    format: Optional[ProductFileFormat] = ProductFileFormat.ATX
    content: Optional[ProductContentType] = ProductContentType.ATT
   
    filename: Optional[str] = None
    directory: Optional[str] = None