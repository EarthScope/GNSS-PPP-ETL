from typing import Optional

from ..base import (
    AssetBase,
    ProductSampleInterval,
    ProductDuration,
)
from ..base.igs_conventions import (
    Rinex3DataType,
    Rinex3DataSource,
    Rinex2DataType,
    Rinex2FileInterval,
    RinexSatelliteSystem,
    RinexVersion,
)

# ---------------------------------------------------------------------------
# Regex fallback patterns for RINEX filename placeholders
# ---------------------------------------------------------------------------

_RINEX_PLACEHOLDER_REGEX: dict[str, str] = {
    "station":          r"[A-Z0-9]{4}",
    "monument":         r"\d",
    "receiver":         r"[A-Z0-9]",
    "region":           r"[A-Z]{3}",
    "data_source":      r"[A-Z]",
    "year":             r"\d{4}",
    "doy":              r"\d{3}",
    "duration":         r"\d{2}[SMHD]",
    "interval":         r"\d{2}[SMHD]",
    "satellite_system": r"[GRECJILM]",
    "content":          r"[A-Z]",
    "gps_week":         r"\d{4}",
    "yy":               r"\d{2}",
    "month":            r"\d{2}",
    "day":              r"\d{2}",
}


class _RegexFallbackDict(dict):
    """Dict that returns regex patterns for unknown RINEX placeholder keys."""

    def __missing__(self, key: str) -> str:
        return _RINEX_PLACEHOLDER_REGEX.get(key, ".+")


class RinexBase(AssetBase):
    """Base class for all RINEX configurations."""
    station: Optional[str] = None
    region: Optional[str] = None
    monument: Optional[int] = None
    receiver: Optional[str] = None
    interval: Optional[ProductSampleInterval | Rinex2FileInterval] = None
    duration: Optional[ProductDuration | Rinex2FileInterval] = None
    satellite_system: Optional[RinexSatelliteSystem] = None
    content: Optional[Rinex3DataType | Rinex2DataType] = None
    version: RinexVersion = RinexVersion.V3
    data_source: Optional[Rinex3DataSource] = Rinex3DataSource.R

    filename: Optional[str] = None
    directory: Optional[str] = None
