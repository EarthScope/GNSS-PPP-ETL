from enum import Enum
from typing import Optional

from ..base import AssetBase


# ---------------------------------------------------------------------------
# Troposphere-specific enums
# ---------------------------------------------------------------------------


class VMFProduct(str, Enum):
    """Vienna Mapping Function product types."""
    VMF1 = "VMF1"
    VMF3 = "VMF3"


class VMFGridResolution(str, Enum):
    """Grid resolution options for VMF products."""
    TWO_POINT_FIVE_BY_TWO = "2.5x2"  # VMF1 only
    ONE_BY_ONE = "1x1"                # VMF3 only
    FIVE_BY_FIVE = "5x5"             # VMF3 only


class VMFHour(str, Enum):
    """6-hourly epoch identifiers for VMF products."""
    H00 = "H00"
    H06 = "H06"
    H12 = "H12"
    H18 = "H18"


# ---------------------------------------------------------------------------
# Regex fallback patterns for troposphere filename placeholders
# ---------------------------------------------------------------------------

_TROPOSPHERE_PLACEHOLDER_REGEX: dict[str, str] = {
    "product":    r"(VMFG|VMF3)",
    "year":       r"\d{4}",
    "month":      r"\d{2}",
    "day":        r"\d{2}",
    "hh":         r"H\d{2}",
    "resolution": r"[0-9.]+x[0-9]+",
}


class _RegexFallbackDict(dict):
    """Dict that returns regex patterns for unknown troposphere placeholder keys."""

    def __missing__(self, key: str) -> str:
        return _TROPOSPHERE_PLACEHOLDER_REGEX.get(key, ".+")


class TroposphereBase(AssetBase):
    """Base class for troposphere (VMF) products."""
    product: Optional[VMFProduct] = None
    resolution: Optional[VMFGridResolution] = None
    hour: Optional[VMFHour] = None

    filename: Optional[str] = None
    directory: Optional[str] = None
