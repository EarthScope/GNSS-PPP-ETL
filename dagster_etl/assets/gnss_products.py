# dagster_etl/assets/gnss_products.py

import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, Optional, Union
import re # Added for regex compilation

from dagster import Config, asset, get_dagster_logger

# Import helper functions and classes from pride_tools
from pride_tools.gnss_product_operations import (
    download,
    uncompress_file,
    update_source,
)
from pride_tools.gnss_product_schemas import RemoteResourceFTP, RemoteQuery # Import RemoteQuery
from pride_tools.pride_file_config import PRIDEPPPFileConfig, SatelliteProducts
from pride_tools.rinex_utils import rinex_get_time_range

# Import classes from gnss_ppp_products for new data source integration
from gnss_ppp_products.utils.product_sources import ProductQuality, ProductSourcePathFTP, ProductSourcesFTP
from gnss_ppp_products.defs.assets import ftp_product_sources # Import the asset itself

class ProductSource(Enum):
    ALL = "all"
    WUHAN = "wuhan"
    CLIGS = "cligs"


class GNSSProductsConfig(Config):
    """
    Configuration for the pride_gnss_products_config asset.
    """
    rinex_path: Optional[str] = None
    """
    The path to the RINEX file. If provided, `date_str` will be ignored.
    """
    pride_dir: str
    """
    The directory where the PRIDE products are stored.
    """
    override: bool = False
    """
    If True, the function will attempt to download the products even if they already exist locally.
    """
    source: ProductSource = ProductSource.ALL
    """
    The source from which to download the products. Defaults to "all".
    """
    date_str: Optional[str] = None
    """
    The date for which to retrieve the products, in YYYY-MM-DD format.
    Required if `rinex_path` is not provided.
    """
    override_config: bool = True
    """
    If True, the function will attempt to re-download the products even if a config file already exists.
    """


@asset(
    deps=[ftp_product_sources], # Added dependency on ftp_product_sources
    description="Generates or retrieves GNSS products and creates a PRIDE config file.",
    metadata={
        "owner": "data_engineering",
        "tags": ["gnss", "pride", "etl"],
    }
)
def pride_gnss_products_config(
    context, 
    config: GNSSProductsConfig,
    all_ftp_sources: Dict[str, ProductSourcesFTP] # New input parameter
) -> Path:
    """
    Generates or retrieves GNSS products for a given RINEX file or date and returns the path
    to a PRIDE config file that catalogs these products.

    This asset encapsulates the functionality of the `get_gnss_products` function
    from `pride_tools.gnss_product_operations`, now leveraging `ftp_product_sources`.
    """
    logger = get_dagster_logger()

    # Determine start_date
    start_date: Optional[datetime.date] = None
    if config.rinex_path:
        rinex_file_path = Path(config.rinex_path)
        logger.info(f"Determining date from RINEX file: {rinex_file_path}")
        try:
            start_date, _ = rinex_get_time_range(rinex_file_path)
        except Exception as e:
            logger.error(f"Failed to read RINEX file {rinex_file_path}: {e}")
            raise
        if start_date is None:
            logger.error(f"No 'TIME OF FIRST OBS' found in RINEX file: {rinex_file_path}")
            raise ValueError("No 'TIME OF FIRST OBS' found in RINEX file.")
    elif config.date_str:
        try:
            start_date = datetime.date.fromisoformat(config.date_str)
            logger.info(f"Using date from config: {start_date}")
        except ValueError as e:
            logger.error(f"Invalid date_str format: {config.date_str}. Expected YYYY-MM-DD. Error: {e}")
            raise
    else:
        raise ValueError("Either 'rinex_path' or 'date_str' must be provided in the asset configuration.")

    year = str(start_date.year)
    doy = str(start_date.timetuple().tm_yday)

    pride_dir_path = Path(config.pride_dir)
    common_product_dir = pride_dir_path / year / "product" / "common"
    common_product_dir.mkdir(exist_ok=True, parents=True)
    logger.info(f"Ensured common product directory exists: {common_product_dir}")

    config_template_file_path = pride_dir_path / year / doy / "config_file"
    config_template = None

    if config_template_file_path.exists():
        logger.info(f"Found existing config file: {config_template_file_path}. Attempting to load and validate.")
        try:
            config_template = PRIDEPPPFileConfig.read_config_file(config_template_file_path)
            product_directory = Path(
                config_template.satellite_products.product_directory
            )
            if not product_directory.exists():
                logger.warning(f"Product directory '{product_directory}' specified in config does not exist. Invalidating existing config.")
                config_template = None # Invalidate config if directory is missing
            else:
                # Check if all products mentioned in the config actually exist
                all_products_exist = True
                for name, product_name_in_config in config_template.satellite_products.model_dump().items():
                    if name not in ["product_directory", "leo_quaternions"] and product_name_in_config is not None:
                        test_path = product_directory / "common" / product_name_in_config
                        if not test_path.exists():
                            logger.warning(f"Product '{name}' (file: '{product_name_in_config}') not found in '{test_path}'. Invalidating existing config.")
                            all_products_exist = False
                            break
                if not all_products_exist:
                    config_template = None
        except Exception as e:
            config_template = None
            logger.warning(
                f"Failed to load or validate config file {config_template_file_path}: {e}. Invalidating existing config."
            )

    if config_template is not None and not config.override_config:
        logger.info(f"Using valid existing config file: {config_template_file_path}")
        return config_template_file_path

    logger.info("Proceeding to download/generate GNSS products and create new config.")
    
    cp_dir_list = list(common_product_dir.glob("*"))
    
    product_status: Dict[str, Optional[str]] = {} # Store only filename here
    
    # Define product types we are interested in for `get_gnss_products` common products
    # Note: 'bias' is not available in `ProductSourcesFTP` from `gnss_ppp_products.utils.product_sources`.
    # We will only process product types available in `ProductSourcesFTP` for now.
    common_product_types = ["sp3", "obx", "clk", "erp"] # Matching attributes in ProductSourcesFTP

    quality_priority = [ProductQuality.FINAL, ProductQuality.RAPID, ProductQuality.REAL_TIME_STREAMING]

    for product_type in common_product_types:
        logger.info(f"Attempting to obtain product: {product_type}")
        product_status[product_type] = None # Initialize

        for quality in quality_priority:
            logger.info(f"  Trying quality level: {quality.value}")
            
            product_found_for_this_quality = False
            for dl_source_name, product_sources_ftp_obj in all_ftp_sources.items():
                if config.source.value != "all" and dl_source_name != config.source.value:
                    continue

                logger.info(f"    From source: {dl_source_name}")

                # Check if the product type exists for this source in ProductSourcesFTP
                if not hasattr(product_sources_ftp_obj, product_type):
                    logger.debug(f"      Product type '{product_type}' not available from source '{dl_source_name}'. Skipping.")
                    continue

                # Get the ProductSourceCollectionFTP for the current product type
                product_collection: ProductSourceCollectionFTP = getattr(product_sources_ftp_obj, product_type)
                
                # Get the specific ProductSourcePathFTP for the current quality level
                product_source_path_ftp: ProductSourcePathFTP = getattr(product_collection, quality.name.lower())

                # Convert to RemoteResourceFTP for compatibility
                remote_query_obj = RemoteQuery(
                    pattern=re.compile(product_source_path_ftp.file_regex),
                    sort_order=None # Sort order not explicitly provided by product_sources.py
                )
                remote_resource = RemoteResourceFTP(
                    ftpserver=product_source_path_ftp.ftpserver,
                    directory=product_source_path_ftp.directory,
                    remote_query=remote_query_obj,
                    file_name=None # Will be filled by update_source
                )

                current_product_downloaded_from_source = False

                # Check if file already exists locally for this specific resource/regex
                current_cp_dir_files = [f for f in cp_dir_list if re.match(product_source_path_ftp.file_regex, f.name)]
                
                if current_cp_dir_files and not config.override:
                    to_decompress = current_cp_dir_files[0]
                    logger.info(f"      Found local file {to_decompress.name} for {product_type} ({quality.value}) from {dl_source_name}. Checking...")
                    decompressed_file = None
                    if to_decompress.suffix == ".gz":
                        try:
                            decompressed_file = uncompress_file(
                                to_decompress, common_product_dir
                            )
                            if decompressed_file is None:
                                logger.warning(
                                    f"      Failed to decompress {to_decompress} for {product_type} ({quality.value}) from {dl_source_name}. Trying next source/quality."
                                )
                            else:
                                logger.info(
                                    f"      Successfully used existing and decompressed file {decompressed_file.name} for {product_type} ({quality.value}) from {dl_source_name}."
                                )
                                product_status[product_type] = str(decompressed_file.name)
                                current_product_downloaded_from_source = True
                        except Exception as e:
                            logger.warning(f"      Error during decompression of {to_decompress}: {e}. Trying next source/quality.")
                    else:
                        decompressed_file = to_decompress
                        logger.info(
                            f"      Using existing file {decompressed_file.name} for {product_type} ({quality.value}) from {dl_source_name}."
                        )
                        product_status[product_type] = str(decompressed_file.name)
                        current_product_downloaded_from_source = True
                
                if current_product_downloaded_from_source:
                    product_found_for_this_quality = True
                    break # Break from dl_source_name loop, product found for this quality
                
                if not product_found_for_this_quality: # Only attempt download if not already found locally
                    remote_resource_updated = update_source(remote_resource)
                    if remote_resource_updated.file_name is None:
                        logger.warning(f"      No remote file found for {product_type} ({quality.value}) from {dl_source_name}.")
                        continue # Try next source for current quality

                    local_path = common_product_dir / remote_resource_updated.file_name
                    try:
                        logger.info(
                            f"      Attempting to download {product_type} ({quality.value}) from {remote_resource_updated.ftpserver}/{remote_resource_updated.directory}/{remote_resource_updated.file_name} to {local_path}"
                        )
                        download(remote_resource_updated, local_path)
                        logger.info(
                            f"      Successfully downloaded {product_type} ({quality.value}) from {dl_source_name} to {local_path.name}."
                        )
                        if local_path.suffix == ".gz":
                            original_compressed_path = local_path
                            local_path = uncompress_file(local_path, common_product_dir)
                            if local_path is None:
                                logger.warning(f"      Failed to uncompress downloaded file {original_compressed_path.name}. Trying next source for current quality.")
                                if original_compressed_path.exists() and original_compressed_path.stat().st_size == 0:
                                    original_compressed_path.unlink()
                                continue
                            logger.info(f"      Uncompressed {original_compressed_path.name} to {local_path.name}.")
                        product_status[product_type] = str(local_path.name)
                        product_found_for_this_quality = True
                        break # Break from dl_source_name loop, product found for this quality
                    except Exception as e:
                        logger.error(f"      Failed to download {product_type} ({quality.value}) from {dl_source_name} | {e}")
                        if local_path.exists() and local_path.stat().st_size == 0:
                            local_path.unlink()
                        continue # Try next source for current quality
            
            if product_found_for_this_quality:
                break # Break from quality loop, product obtained for this product_type

        if product_status.get(product_type) is None:
            logger.warning(f"  Could not obtain product '{product_type}' from any source or quality level specified.")

    for product_type, product_path_name in product_status.items():
        logger.info(f"Final status for {product_type} : {product_path_name if product_path_name else 'Not available'}")

    # Note on 'bias' product:
    # The `ProductSourcesFTP` structure from `gnss_ppp_products.utils.product_sources`
    # does not currently provide 'bias' products. If 'bias' is crucial, `product_sources.py`
    # would need to be extended or a fallback mechanism implemented.
    # For now, `code_phase_bias` in `SatelliteProducts` will be None if not found here.
    if "bias" not in common_product_types:
        logger.warning(
            "The 'bias' product type is not handled by the current `ftp_product_sources` integration. "
            "It will be set to None in the generated PRIDE config file."
        )


    # Generate the config file
    satellite_products = SatelliteProducts(
        satellite_orbit=product_status.get("sp3"),
        satellite_clock=product_status.get("clk"),
        code_phase_bias=product_status.get("bias"), # Will be None as per current product_sources.py
        quaternions=product_status.get("obx"),
        erp=product_status.get("erp"),
        product_directory=str(common_product_dir.parent),
    )
    config_template = PRIDEPPPFileConfig.load_default()
    config_template.satellite_products = satellite_products
    config_template_file_path.parent.mkdir(parents=True, exist_ok=True)
    config_template.write_config_file(config_template_file_path)
    logger.info(f"Generated PRIDE config file: {config_template_file_path}")
    return config_template_file_path

all_assets = [pride_gnss_products_config]