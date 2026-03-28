"""Author: Franklyn Dunbar

pride_ppp — PRIDE PPP-AR integration package.

Provides CLI configuration, subprocess execution, config-file I/O,
output parsing, and product resolution for the PRIDE-PPP-AR GNSS
processing engine.  Product resolution is powered by ``gnss-ppp-products``
dependency resolution.
"""

from .cli import PrideCLIConfig
from .config import PRIDEPPPFileConfig, SatelliteProducts
from .output import PridePPP, kin_to_kin_position_df, validate_kin_file
from .products import get_gnss_products, get_nav_file, resolve_products
from .rinex import merge_broadcast_files
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
    "merge_broadcast_files",
    "resolve_products",
    "rinex_to_kin",
]
