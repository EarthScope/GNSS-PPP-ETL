"""Local resource specification — models and registry."""

from .models import LocalCollection, LocalResourceSpec
from .registry import _LocalResourceRegistry
__all__ = [
    "LocalCollection",
    "LocalResourceSpec",
    "_LocalResourceRegistry",
]
