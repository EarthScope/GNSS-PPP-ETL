"""Author: Franklyn Dunbar

Configs — YAML file paths for the bundled config data.

Provides absolute ``Path`` constants that point at the YAML specification
files shipped inside this package.
"""

from pathlib import Path

_CONFIGS_DIR = Path(__file__).resolve().parent

# Path to the parameter/metadata specification YAML.
META_SPEC_YAML = _CONFIGS_DIR / "meta" / "meta_spec.yaml"
# Path to the product specification YAML.
PRODUCT_SPEC_YAML = _CONFIGS_DIR / "products" / "product_spec.yaml"
# Directory containing local resource layout YAMLs.
LOCAL_SPEC_DIR = _CONFIGS_DIR / "local"
# Path to the query configuration YAML.
QUERY_SPEC_YAML = _CONFIGS_DIR / "query" / "query_config.yaml"
# Directory containing per-center resource YAMLs.
CENTERS_RESOURCE_DIR = _CONFIGS_DIR / "centers"
# Directory containing dependency specification YAMLs.
DEPENDENCY_SPEC_DIR = _CONFIGS_DIR / "dependencies"
# Path to the format specification YAML.
FORMAT_SPEC_YAML = _CONFIGS_DIR / "products" / "format_spec.yaml"
__all__ = [
    "META_SPEC_YAML",
    "PRODUCT_SPEC_YAML",
    "LOCAL_SPEC_DIR",
    "QUERY_SPEC_YAML",
    "CENTERS_RESOURCE_DIR",
    "DEPENDENCY_SPEC_DIR",
    "FORMAT_SPEC_YAML",
]
