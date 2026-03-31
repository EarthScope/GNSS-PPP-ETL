"""Factories — core processing interfaces for PRIDE-PPPAR.

Submodules
~~~~~~~~~~
- :mod:`.processor` — ``PrideProcessor``, ``ProcessingResult``, ``ProcessingMode``
- :mod:`.output`    — ``.kin`` / ``.res`` file parsing and validation
- :mod:`.rinex`     — RINEX timestamp extraction and broadcast-file merging
"""

from pride_ppp.factories.output import (
    get_wrms_from_res,
    kin_to_kin_position_df,
    plot_kin_results_wrms,
    read_kin_data,
    validate_kin_file,
)
from pride_ppp.factories.processor import (
    PrideProcessor,
    ProcessingMode,
    ProcessingResult,
)
from pride_ppp.factories.rinex import merge_broadcast_files, rinex_get_time_range

__all__ = [
    "PrideProcessor",
    "ProcessingMode",
    "ProcessingResult",
    "get_wrms_from_res",
    "kin_to_kin_position_df",
    "plot_kin_results_wrms",
    "read_kin_data",
    "validate_kin_file",
    "merge_broadcast_files",
    "rinex_get_time_range",
]
