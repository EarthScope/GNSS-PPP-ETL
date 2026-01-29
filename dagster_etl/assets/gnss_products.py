"""Dagster assets for GNSS product downloads."""

import datetime
from pathlib import Path
from typing import Dict, List, Optional

from dagster import (
    AssetExecutionContext,
    Config,
    MetadataValue,
    Output,
    asset,
)
from pydantic import Field

from pride_tools.gnss_product_operations import (
    download,
    get_gnss_common_products_urls,
    uncompress_file,
    update_source,
)
from pride_tools.gnss_product_schemas import RemoteResourceFTP
from pride_tools.pride_file_config import PRIDEPPPFileConfig, SatelliteProducts


class GNSSProductConfig(Config):
    """Configuration for GNSS product downloads."""

    date: str = Field(
        description="Date for which to download products (YYYY-MM-DD format)"
    )
    pride_dir: str = Field(description="Directory to store PRIDE products")
    override: bool = Field(
        default=False, description="Re-download products even if they exist"
    )
    source: str = Field(
        default="all",
        description="Source to download from: 'all', 'wuhan', or 'cligs'",
    )


@asset(
    description="Download and process satellite orbit files (SP3)",
    compute_kind="python",
)
def satellite_orbit_sp3(
    context: AssetExecutionContext, config: GNSSProductConfig
) -> Output[Path]:
    """Download satellite orbit (SP3) files."""
    date = datetime.datetime.strptime(config.date, "%Y-%m-%d").date()
    pride_dir = Path(config.pride_dir)
    year = str(date.year)
    doy = str(date.timetuple().tm_yday)

    common_product_dir = pride_dir / year / "product" / "common"
    common_product_dir.mkdir(exist_ok=True, parents=True)

    product_urls = get_gnss_common_products_urls(date)
    sp3_sources = product_urls["sp3"]

    downloaded_file = None
    for source_name, remote_resource in sp3_sources.items():
        if config.source != "all" and source_name != config.source:
            continue

        context.log.info(f"Attempting to download SP3 from {source_name}")
        remote_resource_updated = update_source(remote_resource)

        if remote_resource_updated.file_name is None:
            context.log.warning(f"No file found for SP3 from {source_name}")
            continue

        local_path = common_product_dir / remote_resource_updated.file_name

        if local_path.exists() and not config.override:
            context.log.info(f"SP3 file already exists: {local_path}")
            downloaded_file = local_path
            break

        try:
            download(remote_resource_updated, local_path)
            if local_path.suffix == ".gz":
                local_path = uncompress_file(local_path, common_product_dir)
            downloaded_file = local_path
            context.log.info(f"Successfully downloaded SP3: {local_path}")
            break
        except Exception as e:
            context.log.error(f"Failed to download SP3 from {source_name}: {e}")
            continue

    if downloaded_file is None:
        raise RuntimeError("Failed to download SP3 file from any source")

    return Output(
        downloaded_file,
        metadata={
            "file_path": str(downloaded_file),
            "file_size": downloaded_file.stat().st_size,
            "source": config.source,
            "date": config.date,
        },
    )


@asset(
    description="Download and process satellite clock files (CLK)",
    compute_kind="python",
)
def satellite_clock_clk(
    context: AssetExecutionContext, config: GNSSProductConfig
) -> Output[Path]:
    """Download satellite clock (CLK) files."""
    date = datetime.datetime.strptime(config.date, "%Y-%m-%d").date()
    pride_dir = Path(config.pride_dir)
    year = str(date.year)

    common_product_dir = pride_dir / year / "product" / "common"
    common_product_dir.mkdir(exist_ok=True, parents=True)

    product_urls = get_gnss_common_products_urls(date)
    clk_sources = product_urls["clk"]

    downloaded_file = None
    for source_name, remote_resource in clk_sources.items():
        if config.source != "all" and source_name != config.source:
            continue

        context.log.info(f"Attempting to download CLK from {source_name}")
        remote_resource_updated = update_source(remote_resource)

        if remote_resource_updated.file_name is None:
            context.log.warning(f"No file found for CLK from {source_name}")
            continue

        local_path = common_product_dir / remote_resource_updated.file_name

        if local_path.exists() and not config.override:
            context.log.info(f"CLK file already exists: {local_path}")
            downloaded_file = local_path
            break

        try:
            download(remote_resource_updated, local_path)
            if local_path.suffix == ".gz":
                local_path = uncompress_file(local_path, common_product_dir)
            downloaded_file = local_path
            context.log.info(f"Successfully downloaded CLK: {local_path}")
            break
        except Exception as e:
            context.log.error(f"Failed to download CLK from {source_name}: {e}")
            continue

    if downloaded_file is None:
        raise RuntimeError("Failed to download CLK file from any source")

    return Output(
        downloaded_file,
        metadata={
            "file_path": str(downloaded_file),
            "file_size": downloaded_file.stat().st_size,
            "source": config.source,
            "date": config.date,
        },
    )


@asset(
    description="Download and process code/phase bias files",
    compute_kind="python",
)
def code_phase_bias(
    context: AssetExecutionContext, config: GNSSProductConfig
) -> Output[Path]:
    """Download code/phase bias files."""
    date = datetime.datetime.strptime(config.date, "%Y-%m-%d").date()
    pride_dir = Path(config.pride_dir)
    year = str(date.year)

    common_product_dir = pride_dir / year / "product" / "common"
    common_product_dir.mkdir(exist_ok=True, parents=True)

    product_urls = get_gnss_common_products_urls(date)
    bias_sources = product_urls["bias"]

    downloaded_file = None
    for source_name, remote_resource in bias_sources.items():
        if config.source != "all" and source_name != config.source:
            continue

        context.log.info(f"Attempting to download BIAS from {source_name}")
        remote_resource_updated = update_source(remote_resource)

        if remote_resource_updated.file_name is None:
            context.log.warning(f"No file found for BIAS from {source_name}")
            continue

        local_path = common_product_dir / remote_resource_updated.file_name

        if local_path.exists() and not config.override:
            context.log.info(f"BIAS file already exists: {local_path}")
            downloaded_file = local_path
            break

        try:
            download(remote_resource_updated, local_path)
            if local_path.suffix == ".gz":
                local_path = uncompress_file(local_path, common_product_dir)
            downloaded_file = local_path
            context.log.info(f"Successfully downloaded BIAS: {local_path}")
            break
        except Exception as e:
            context.log.error(f"Failed to download BIAS from {source_name}: {e}")
            continue

    if downloaded_file is None:
        raise RuntimeError("Failed to download BIAS file from any source")

    return Output(
        downloaded_file,
        metadata={
            "file_path": str(downloaded_file),
            "file_size": downloaded_file.stat().st_size,
            "source": config.source,
            "date": config.date,
        },
    )


@asset(
    description="Download and process quaternion files (OBX)",
    compute_kind="python",
)
def quaternions_obx(
    context: AssetExecutionContext, config: GNSSProductConfig
) -> Output[Path]:
    """Download quaternion (OBX) files."""
    date = datetime.datetime.strptime(config.date, "%Y-%m-%d").date()
    pride_dir = Path(config.pride_dir)
    year = str(date.year)

    common_product_dir = pride_dir / year / "product" / "common"
    common_product_dir.mkdir(exist_ok=True, parents=True)

    product_urls = get_gnss_common_products_urls(date)
    obx_sources = product_urls["obx"]

    downloaded_file = None
    for source_name, remote_resource in obx_sources.items():
        if config.source != "all" and source_name != config.source:
            continue

        context.log.info(f"Attempting to download OBX from {source_name}")
        remote_resource_updated = update_source(remote_resource)

        if remote_resource_updated.file_name is None:
            context.log.warning(f"No file found for OBX from {source_name}")
            continue

        local_path = common_product_dir / remote_resource_updated.file_name

        if local_path.exists() and not config.override:
            context.log.info(f"OBX file already exists: {local_path}")
            downloaded_file = local_path
            break

        try:
            download(remote_resource_updated, local_path)
            if local_path.suffix == ".gz":
                local_path = uncompress_file(local_path, common_product_dir)
            downloaded_file = local_path
            context.log.info(f"Successfully downloaded OBX: {local_path}")
            break
        except Exception as e:
            context.log.error(f"Failed to download OBX from {source_name}: {e}")
            continue

    if downloaded_file is None:
        raise RuntimeError("Failed to download OBX file from any source")

    return Output(
        downloaded_file,
        metadata={
            "file_path": str(downloaded_file),
            "file_size": downloaded_file.stat().st_size,
            "source": config.source,
            "date": config.date,
        },
    )


@asset(
    description="Download and process Earth rotation parameter files (ERP)",
    compute_kind="python",
)
def earth_rotation_parameters_erp(
    context: AssetExecutionContext, config: GNSSProductConfig
) -> Output[Path]:
    """Download Earth rotation parameter (ERP) files."""
    date = datetime.datetime.strptime(config.date, "%Y-%m-%d").date()
    pride_dir = Path(config.pride_dir)
    year = str(date.year)

    common_product_dir = pride_dir / year / "product" / "common"
    common_product_dir.mkdir(exist_ok=True, parents=True)

    product_urls = get_gnss_common_products_urls(date)
    erp_sources = product_urls["erp"]

    downloaded_file = None
    for source_name, remote_resource in erp_sources.items():
        if config.source != "all" and source_name != config.source:
            continue

        context.log.info(f"Attempting to download ERP from {source_name}")
        remote_resource_updated = update_source(remote_resource)

        if remote_resource_updated.file_name is None:
            context.log.warning(f"No file found for ERP from {source_name}")
            continue

        local_path = common_product_dir / remote_resource_updated.file_name

        if local_path.exists() and not config.override:
            context.log.info(f"ERP file already exists: {local_path}")
            downloaded_file = local_path
            break

        try:
            download(remote_resource_updated, local_path)
            if local_path.suffix == ".gz":
                local_path = uncompress_file(local_path, common_product_dir)
            downloaded_file = local_path
            context.log.info(f"Successfully downloaded ERP: {local_path}")
            break
        except Exception as e:
            context.log.error(f"Failed to download ERP from {source_name}: {e}")
            continue

    if downloaded_file is None:
        raise RuntimeError("Failed to download ERP file from any source")

    return Output(
        downloaded_file,
        metadata={
            "file_path": str(downloaded_file),
            "file_size": downloaded_file.stat().st_size,
            "source": config.source,
            "date": config.date,
        },
    )


@asset(
    description="Generate PRIDE-PPP configuration file from downloaded products",
    compute_kind="python",
    deps=[
        satellite_orbit_sp3,
        satellite_clock_clk,
        code_phase_bias,
        quaternions_obx,
        earth_rotation_parameters_erp,
    ],
)
def pride_config_file(
    context: AssetExecutionContext,
    config: GNSSProductConfig,
    satellite_orbit_sp3: Path,
    satellite_clock_clk: Path,
    code_phase_bias: Path,
    quaternions_obx: Path,
    earth_rotation_parameters_erp: Path,
) -> Output[Path]:
    """Generate PRIDE-PPP configuration file from downloaded GNSS products."""
    date = datetime.datetime.strptime(config.date, "%Y-%m-%d").date()
    pride_dir = Path(config.pride_dir)
    year = str(date.year)
    doy = str(date.timetuple().tm_yday)

    common_product_dir = pride_dir / year / "product" / "common"

    # Create satellite products configuration
    satellite_products = SatelliteProducts(
        satellite_orbit=satellite_orbit_sp3.name,
        satellite_clock=satellite_clock_clk.name,
        code_phase_bias=code_phase_bias.name,
        quaternions=quaternions_obx.name,
        erp=earth_rotation_parameters_erp.name,
        product_directory=str(common_product_dir.parent),
    )

    # Load default config and update with our products
    config_template = PRIDEPPPFileConfig.load_default()
    config_template.satellite_products = satellite_products

    # Write config file
    config_file_path = pride_dir / year / doy / "config_file"
    config_file_path.parent.mkdir(exist_ok=True, parents=True)
    config_template.write_config_file(config_file_path)

    context.log.info(f"Generated PRIDE config file: {config_file_path}")

    return Output(
        config_file_path,
        metadata={
            "config_path": str(config_file_path),
            "sp3_file": satellite_orbit_sp3.name,
            "clk_file": satellite_clock_clk.name,
            "bias_file": code_phase_bias.name,
            "obx_file": quaternions_obx.name,
            "erp_file": earth_rotation_parameters_erp.name,
        },
    )


# Export all assets
all_assets = [
    satellite_orbit_sp3,
    satellite_clock_clk,
    code_phase_bias,
    quaternions_obx,
    earth_rotation_parameters_erp,
    pride_config_file,
]
