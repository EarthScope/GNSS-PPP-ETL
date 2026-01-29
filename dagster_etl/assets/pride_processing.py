"""Dagster assets for PRIDE-PPP processing."""

import datetime
from pathlib import Path
from typing import Tuple

from dagster import (
    AssetExecutionContext,
    Config,
    MetadataValue,
    Output,
    asset,
)
from pydantic import Field

from pride_tools.pride_cli_config import PrideCLIConfig
from pride_tools.pride_operations import rinex_to_kin
from pride_tools.kin_file_operations import (
    kin_to_kin_position_df,
    validate_kin_file,
    get_wrms_from_res,
)


class PRIDEProcessingConfig(Config):
    """Configuration for PRIDE-PPP processing."""

    rinex_file: str = Field(description="Path to RINEX observation file")
    pride_dir: str = Field(description="Directory containing PRIDE products")
    output_dir: str = Field(description="Directory to write output files")
    site: str = Field(default="SIT1", description="Site identifier")
    sample_frequency: int = Field(
        default=30, description="Sample frequency in seconds"
    )
    override: bool = Field(
        default=False, description="Override existing processed files"
    )


@asset(
    description="Process RINEX file to generate kinematic position (KIN) and residual (RES) files using PRIDE-PPP",
    compute_kind="pride-ppp",
)
def process_rinex_to_kin(
    context: AssetExecutionContext,
    config: PRIDEProcessingConfig,
    pride_config_file: Path,
) -> Output[Tuple[Path, Path]]:
    """
    Process RINEX observation file using PRIDE-PPP to generate KIN and RES files.

    Args:
        context: Dagster execution context
        config: Processing configuration
        pride_config_file: Path to PRIDE configuration file (from upstream asset)

    Returns:
        Tuple of (kin_file_path, res_file_path)
    """
    rinex_path = Path(config.rinex_file)
    pride_dir = Path(config.pride_dir)
    output_dir = Path(config.output_dir)

    # Ensure output directory exists
    output_dir.mkdir(exist_ok=True, parents=True)

    # Create PRIDE CLI configuration
    pride_cli_config = PrideCLIConfig(
        sample_frequency=config.sample_frequency,
        override=config.override,
        pride_configfile_path=pride_config_file,
    )

    context.log.info(f"Processing RINEX file: {rinex_path}")
    context.log.info(f"Using PRIDE config: {pride_config_file}")
    context.log.info(f"Site: {config.site}")

    # Process RINEX file
    kin_file, res_file = rinex_to_kin(
        source=str(rinex_path),
        writedir=output_dir,
        pridedir=pride_dir,
        site=config.site,
        pride_cli_config=pride_cli_config,
    )

    if kin_file is None:
        raise RuntimeError(f"Failed to process RINEX file: {rinex_path}")

    context.log.info(f"Generated KIN file: {kin_file}")
    if res_file:
        context.log.info(f"Generated RES file: {res_file}")

    metadata = {
        "kin_file": str(kin_file),
        "kin_file_size": kin_file.stat().st_size if kin_file else 0,
        "res_file": str(res_file) if res_file else "Not generated",
        "res_file_size": res_file.stat().st_size if res_file else 0,
        "site": config.site,
        "rinex_file": str(rinex_path),
    }

    return Output((kin_file, res_file), metadata=metadata)


@asset(
    description="Convert KIN file to pandas DataFrame with position data",
    compute_kind="python",
)
def kin_position_dataframe(
    context: AssetExecutionContext,
    process_rinex_to_kin: Tuple[Path, Path],
) -> Output:
    """
    Convert KIN file to a pandas DataFrame.

    Args:
        context: Dagster execution context
        process_rinex_to_kin: Tuple of (kin_file, res_file) from upstream asset

    Returns:
        Path to saved CSV file
    """
    kin_file, res_file = process_rinex_to_kin

    if not validate_kin_file(kin_file):
        raise RuntimeError(f"KIN file validation failed: {kin_file}")

    context.log.info(f"Converting KIN file to DataFrame: {kin_file}")

    # Convert KIN to DataFrame
    df = kin_to_kin_position_df(kin_file)

    if df is None or df.empty:
        raise RuntimeError(f"Failed to convert KIN file to DataFrame: {kin_file}")

    # Save DataFrame as CSV
    csv_path = kin_file.with_suffix(".csv")
    df.to_csv(csv_path, index=False)

    context.log.info(f"Saved position data to CSV: {csv_path}")

    # Calculate some statistics
    num_records = len(df)
    time_range = (df["time"].min(), df["time"].max()) if "time" in df.columns else None

    metadata = {
        "csv_file": str(csv_path),
        "num_records": num_records,
        "time_start": str(time_range[0]) if time_range else "N/A",
        "time_end": str(time_range[1]) if time_range else "N/A",
        "columns": ", ".join(df.columns.tolist()),
        "preview": MetadataValue.md(df.head(10).to_markdown()),
    }

    # Add position statistics if available
    if all(col in df.columns for col in ["latitude", "longitude", "height"]):
        metadata.update(
            {
                "mean_latitude": float(df["latitude"].mean()),
                "mean_longitude": float(df["longitude"].mean()),
                "mean_height": float(df["height"].mean()),
                "std_height": float(df["height"].std()),
            }
        )

    return Output(csv_path, metadata=metadata)


@asset(
    description="Extract WRMS (Weighted Root Mean Square) statistics from RES file",
    compute_kind="python",
)
def residual_statistics(
    context: AssetExecutionContext,
    process_rinex_to_kin: Tuple[Path, Path],
) -> Output:
    """
    Extract WRMS statistics from residual (RES) file.

    Args:
        context: Dagster execution context
        process_rinex_to_kin: Tuple of (kin_file, res_file) from upstream asset

    Returns:
        Dictionary containing WRMS statistics
    """
    kin_file, res_file = process_rinex_to_kin

    if res_file is None or not res_file.exists():
        context.log.warning("No RES file available for statistics")
        return Output(
            {},
            metadata={
                "status": "No RES file",
                "kin_file": str(kin_file),
            },
        )

    context.log.info(f"Extracting WRMS statistics from: {res_file}")

    try:
        wrms_stats = get_wrms_from_res(res_file)

        if wrms_stats:
            context.log.info(f"WRMS statistics: {wrms_stats}")

            metadata = {
                "res_file": str(res_file),
                "wrms_stats": MetadataValue.md(
                    "\n".join([f"- **{k}**: {v}" for k, v in wrms_stats.items()])
                ),
            }

            # Add individual metrics
            for key, value in wrms_stats.items():
                metadata[f"wrms_{key}"] = value

            return Output(wrms_stats, metadata=metadata)
        else:
            context.log.warning("No WRMS statistics found in RES file")
            return Output({}, metadata={"status": "No statistics found"})

    except Exception as e:
        context.log.error(f"Error extracting WRMS statistics: {e}")
        return Output({}, metadata={"error": str(e)})


# Export all assets
all_assets = [
    process_rinex_to_kin,
    kin_position_dataframe,
    residual_statistics,
]
