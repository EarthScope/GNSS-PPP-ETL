"""Author: Franklyn Dunbar

Utilities — domain helper functions for GNSS product metadata.
"""

from .metadata_funcs import register_computed_fields, IGSAntexReferenceFrameType
from .paths import as_path, AnyPath

__all__ = [
    "register_computed_fields",
    "IGSAntexReferenceFrameType",
    "as_path",
    "AnyPath",
]
