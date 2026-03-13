"""
pride_ppp — PRIDE PPP-AR integration package.

Provides CLI configuration, subprocess execution, config-file I/O,
and output parsing for the PRIDE-PPP-AR GNSS processing engine.
"""

from .cli import PrideCLIConfig
from .config import PRIDEPPPFileConfig, SatelliteProducts
from .output import PridePPP, kin_to_kin_position_df, validate_kin_file
from .products import get_gnss_products, get_nav_file
from .runner import rinex_to_kin

__all__ = [
    "PrideCLIConfig",
    "PRIDEPPPFileConfig",
    "SatelliteProducts",
    "PridePPP",
    "kin_to_kin_position_df",
    "validate_kin_file",
    "get_gnss_products",
    "get_nav_file",
    "rinex_to_kin",
]
