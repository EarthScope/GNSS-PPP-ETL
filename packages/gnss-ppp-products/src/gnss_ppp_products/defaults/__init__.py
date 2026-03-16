"""
Configs — YAML file paths and singleton factories.

This package bridges between agnostic specification code and the
concrete YAML configuration files that ship with the distribution.
All global singleton registries live here.
"""

from pathlib import Path

# ------------------------------------------------------------------
# YAML file locations (reference the originals in assets/)
# ------------------------------------------------------------------

_ASSETS_DIR = Path(__file__).resolve().parent

META_SPEC_YAML = _ASSETS_DIR / "meta" / "meta_spec.yaml"
PRODUCT_SPEC_YAML = _ASSETS_DIR / "products" / "product_spec.yaml"
LOCAL_SPEC_YAML = _ASSETS_DIR / "local" / "local_v2.yml"
QUERY_SPEC_YAML = _ASSETS_DIR / "query" / "query_v2.yaml"
REMOTE_SPEC_DIR = _ASSETS_DIR / "centers"
DEPENDENCY_SPEC_DIR = _ASSETS_DIR / "tasks"

# ------------------------------------------------------------------
# Lazy singleton access — import from defaults when needed
# ------------------------------------------------------------------

from .defaults import (  # noqa: E402
    MetaDataRegistry,
    ProductSpecRegistry,
    RemoteResourceRegistry,
    LocalResourceRegistry,
    QuerySpecRegistry,
)

__all__ = [
    "META_SPEC_YAML",
    "PRODUCT_SPEC_YAML",
    "LOCAL_SPEC_YAML",
    "QUERY_SPEC_YAML",
    "REMOTE_SPEC_DIR",
    "DEPENDENCY_SPEC_DIR",
    "MetaDataRegistry",
    "ProductSpecRegistry",
    "RemoteResourceRegistry",
    "LocalResourceRegistry",
    "QuerySpecRegistry",
]
