"""Dagster ETL for GNSS-PPP Processing Pipeline."""

from dagster import Definitions

from .assets import gnss_products, pride_processing
from gnss_ppp_products.defs.assets import get_date, ftp_product_sources # Import new assets
from .jobs import daily_gnss_processing_job
from .resources import gnss_config_resource
from .schedules import daily_gnss_schedule

defs = Definitions(
    assets=[get_date, ftp_product_sources, *gnss_products.all_assets, *pride_processing.all_assets], # Add new assets
    jobs=[daily_gnss_processing_job],
    schedules=[daily_gnss_schedule],
    resources={
        "gnss_config": gnss_config_resource,
    },
)