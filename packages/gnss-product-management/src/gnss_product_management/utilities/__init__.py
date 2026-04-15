"""Utilities — domain helper functions for GNSS product metadata."""

from .metadata_funcs import IGSAntexReferenceFrameType, register_computed_fields
from .paths import AnyPath, as_path

__all__ = [
    "register_computed_fields",
    "IGSAntexReferenceFrameType",
    "as_path",
    "AnyPath",
]
