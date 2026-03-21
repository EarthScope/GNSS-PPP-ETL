"""Configs — YAML file paths for the bundled config data.

Use :class:`~gnss_ppp_products.factories.ProductEnvironment` to wire
these configs into live catalogs and factories.
"""

from pathlib import Path

_CONFIGS_DIR = Path(__file__).resolve().parent

META_SPEC_YAML = _CONFIGS_DIR / "meta" / "meta_spec.yaml"
PRODUCT_SPEC_YAML = _CONFIGS_DIR / "products" / "product_spec.yaml"
LOCAL_SPEC_DIR = _CONFIGS_DIR / "local"
QUERY_SPEC_YAML = _CONFIGS_DIR / "query" / "query_config.yaml"
CENTERS_DIR = _CONFIGS_DIR / "centers"
DEPENDENCY_SPEC_DIR = _CONFIGS_DIR / "dependencies"

__all__ = [
    "META_SPEC_YAML",
    "PRODUCT_SPEC_YAML",
    "LOCAL_SPEC_DIR",
    "QUERY_SPEC_YAML",
    "CENTERS_DIR",
    "DEPENDENCY_SPEC_DIR",
]
