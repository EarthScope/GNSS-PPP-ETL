from enum import Enum
from typing import Optional

from ..base import AssetBase


# ---------------------------------------------------------------------------
# Orography-specific enums
# ---------------------------------------------------------------------------


class OrographyGridResolution(str, Enum):
    """Grid resolution options for orography files."""
    ONE_BY_ONE = "1x1"
    FIVE_BY_FIVE = "5x5"


# ---------------------------------------------------------------------------
# Regex fallback patterns for orography filename placeholders
# ---------------------------------------------------------------------------

_OROGRAPHY_PLACEHOLDER_REGEX: dict[str, str] = {
    "resolution": r"[0-9]+x[0-9]+",
}


class _RegexFallbackDict(dict):
    """Dict that returns regex patterns for unknown orography placeholder keys."""

    def __missing__(self, key: str) -> str:
        return _OROGRAPHY_PLACEHOLDER_REGEX.get(key, ".+")


class OrographyBase(AssetBase):
    """Base class for orography (terrain height) grid files."""
    resolution: Optional[OrographyGridResolution] = None

    filename: Optional[str] = None
    directory: Optional[str] = None
