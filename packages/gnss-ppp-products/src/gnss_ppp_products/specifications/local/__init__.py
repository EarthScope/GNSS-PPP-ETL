"""Local resource specification — models and registry."""

from .models import TemporalCategory, LocalCollection, LocalResourceSpec
from .registry import _LocalResourceRegistry

__all__ = [
    "TemporalCategory",
    "LocalCollection",
    "LocalResourceSpec",
    "_LocalResourceRegistry",
]
