"""
Dagster Definitions for the gnss_ppp_products pipeline.

Registers all assets from ``defs/assets.py`` and binds the
``GNSSOutputResource`` so Dagster knows where to write downloaded files
and the generated PRIDE PPP-AR config.

Configuration
-------------
Override the output directory at launch time via the Dagster UI or the
``GNSS_OUTPUT_DIR`` environment variable::

    GNSS_OUTPUT_DIR=/data/gnss dagster dev

Or set it statically in this file for local development.
"""
import dagster as dg
import os

from .defs.assets import all_assets
from .resources import GNSSOutputResource


defs = dg.Definitions(
    assets=all_assets,
    resources={
        # Key must match the parameter name used in asset functions
        # (gnss_output: GNSSOutputResource)
        "gnss_output": GNSSOutputResource(
            output_base_dir=os.environ.get("GNSS_OUTPUT_DIR", "/data/gnss_products")
        ),
    },
)
