"""Bundled YAML config paths for the pride_ppp package."""

from pathlib import Path

_CONFIGS_DIR = Path(__file__).resolve().parent.parent / "configs"

PRIDE_PPPAR_SPEC = _CONFIGS_DIR / "dependencies" / "pride_pppar.yaml"
PRIDE_DIR_SPEC = _CONFIGS_DIR / "local" / "pride_config.yaml"
PRIDE_INSTALL_SPEC = _CONFIGS_DIR / "local" / "pride_install_config.yaml"
PRIDE_PRODUCT_SPEC = _CONFIGS_DIR / "products" / "pride_product_spec.yaml"
PRIDE_CENTERS_DIR = _CONFIGS_DIR / "centers"

__all__ = [
    "PRIDE_PPPAR_SPEC",
    "PRIDE_DIR_SPEC",
    "PRIDE_INSTALL_SPEC",
    "PRIDE_PRODUCT_SPEC",
    "PRIDE_CENTERS_DIR",
]
