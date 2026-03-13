from enum import Enum
from typing import Optional

from ..base import AssetBase


# ---------------------------------------------------------------------------
# LEO-specific enums
# ---------------------------------------------------------------------------


class GRACEMission(str, Enum):
    """GRACE mission identifiers."""
    GRACE = "grace"        # Original GRACE mission (2002-2017)
    GRACE_FO = "grace-fo"  # GRACE Follow-On mission (2018+)


class GRACEInstrument(str, Enum):
    """GRACE/GRACE-FO Level-1B instrument types."""
    ACC = "ACC"  # Accelerometer
    AHK = "AHK"  # Attitude and Housekeeping
    GNV = "GNV"  # GPS Navigation
    KBR = "KBR"  # K-Band Ranging
    LRI = "LRI"  # Laser Ranging Interferometer (GRACE-FO only)
    SCA = "SCA"  # Star Camera Assembly
    THR = "THR"  # Thruster
    CLK = "CLK"  # Clock
    GPS = "GPS"  # GPS data
    MAS = "MAS"  # Mass change
    TIM = "TIM"  # Time


# ---------------------------------------------------------------------------
# Regex fallback patterns for LEO filename placeholders
# ---------------------------------------------------------------------------

_LEO_PLACEHOLDER_REGEX: dict[str, str] = {
    "mission":    r"(grace|grace-fo)",
    "instrument": r"[A-Z]{3}1B",
    "year":       r"\d{4}",
    "month":      r"\d{2}",
    "day":        r"\d{2}",
    "release":    r"RL\d{2}",
    "spacecraft": r"[CD]",
}


class _RegexFallbackDict(dict):
    """Dict that returns regex patterns for unknown LEO placeholder keys."""

    def __missing__(self, key: str) -> str:
        return _LEO_PLACEHOLDER_REGEX.get(key, ".+")


class LEOBase(AssetBase):
    """Base class for LEO satellite (GRACE/GRACE-FO) products."""
    mission: Optional[GRACEMission] = None
    instrument: Optional[GRACEInstrument] = None

    filename: Optional[str] = None
    directory: Optional[str] = None
