from enum import Enum
from typing import Optional

from ..base import AssetBase


# ---------------------------------------------------------------------------
# Reference-table-specific enums
# ---------------------------------------------------------------------------


class ReferenceTableType(str, Enum):
    """Types of reference tables available."""
    LEAP_SECONDS = "leap_seconds"
    SAT_PARAMETERS = "sat_parameters"


# ---------------------------------------------------------------------------
# Regex fallback patterns (minimal — these are mostly static paths)
# ---------------------------------------------------------------------------

_REFTABLE_PLACEHOLDER_REGEX: dict[str, str] = {
    "table_type": r".+",
}


class _RegexFallbackDict(dict):
    """Dict that returns regex patterns for unknown reference table placeholder keys."""

    def __missing__(self, key: str) -> str:
        return _REFTABLE_PLACEHOLDER_REGEX.get(key, ".+")


class ReferenceTableBase(AssetBase):
    """Base class for reference table files (leap seconds, satellite parameters)."""
    table_type: Optional[ReferenceTableType] = None

    filename: Optional[str] = None
    directory: Optional[str] = None
