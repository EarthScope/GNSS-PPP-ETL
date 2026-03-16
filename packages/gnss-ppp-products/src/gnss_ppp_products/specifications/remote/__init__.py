"""Remote resource specification — models and registry."""

from .models import Server, RemoteProduct, RemoteResourceSpec
from .registry import _RemoteResourceRegistry

__all__ = [
    "Server",
    "RemoteProduct",
    "RemoteResourceSpec",
    "_RemoteResourceRegistry",
]
