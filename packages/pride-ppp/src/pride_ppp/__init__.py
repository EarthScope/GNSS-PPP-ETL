"""Author: Franklyn Dunbar

pride_ppp — PRIDE PPP-AR integration package.

Provides a concurrent-safe ``PrideProcessor`` that resolves GNSS products,
runs the pdp3 binary, and returns structured ``ProcessingResult`` objects
with lazy DataFrame access for kinematic positions and residuals.

Lower-level utilities (CLI config, config-file I/O, output parsing, RINEX
helpers) are re-exported for advanced use cases.
"""

from .cli import PrideCLIConfig
from .config import PRIDEPPPFileConfig, SatelliteProducts
from .output import (
    PridePPP,
    get_wrms_from_res,
    kin_to_kin_position_df,
    plot_kin_results_wrms,
    read_kin_data,
    validate_kin_file,
)
from .processor import PrideProcessor, ProcessingResult
from .rinex import merge_broadcast_files, rinex_get_time_range

__all__ = [
    # Primary API
    "PrideProcessor",
    "ProcessingResult",
    # CLI / config
    "PrideCLIConfig",
    "PRIDEPPPFileConfig",
    "SatelliteProducts",
    # Output parsing
    "PridePPP",
    "kin_to_kin_position_df",
    "validate_kin_file",
    "get_wrms_from_res",
    "plot_kin_results_wrms",
    "read_kin_data",
    # RINEX utilities
    "merge_broadcast_files",
    "rinex_get_time_range",
]
