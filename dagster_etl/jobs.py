"""Dagster jobs for GNSS processing."""

from dagster import define_asset_job, AssetSelection

# Job to process all GNSS products and PRIDE processing
daily_gnss_processing_job = define_asset_job(
    name="daily_gnss_processing_job",
    description="Daily job to download GNSS products and process RINEX files",
    selection=AssetSelection.all(),
)

# Job for only GNSS product downloads
gnss_products_only_job = define_asset_job(
    name="gnss_products_only_job",
    description="Job to download GNSS products only",
    selection=AssetSelection.groups("gnss_products"),
)

# Job for only PRIDE processing (assumes products are already available)
pride_processing_only_job = define_asset_job(
    name="pride_processing_only_job",
    description="Job to process RINEX files with PRIDE-PPP",
    selection=AssetSelection.groups("pride_processing"),
)
