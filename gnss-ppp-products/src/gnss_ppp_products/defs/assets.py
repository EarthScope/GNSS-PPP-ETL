"""
Dagster asset graph for the GNSS PPP-AR ETL pipeline.

Asset graph
-----------
::

    gnss_product_sources  (load sources.yml for partition date — no FTP)
            │
    ┌───────┼───────────────────────────────┐
    │       │                               │
  downloaded_sp3   downloaded_clk  ...   downloaded_broadcast_nav
  downloaded_obx   downloaded_erp
  downloaded_bias
    │       │                               │
    └───────┴───────────────────────────────┘
                            │
                    pride_ppp_config   (write PRIDE PPP-AR config file)

The five collection-product assets (sp3, clk, obx, erp, bias) are produced
by a factory so each has a distinct name while sharing identical logic.
All six download assets are independent and run in parallel inside a single
Dagster run.

Quality/source fallback strategy
---------------------------------
* Quality : FINAL → RAPID → REAL_TIME_STREAMING
* Server  : Wuhan IGS → CLIGS
The FTP directory is listed only once per server visit; all quality-level
regex patterns are tested against that cached listing to minimise connections.
"""
from __future__ import annotations

import datetime
from pathlib import Path
from typing import Optional

import dagster as dg
from dagster import AssetExecutionContext

from ..resources import GNSSOutputResource
from ..utils import load_product_sources_FTP
from ..utils.ftp_download import (
    download_broadcast_nav_with_fallback,
    download_product_with_fallback,
)
from ..utils.pride_config import PRIDEPPPFileConfig, ObservationConfig, SatelliteProducts
from ..utils.validation import validate_product_file

# ---------------------------------------------------------------------------
# Partition definition
# ---------------------------------------------------------------------------
# end_offset=-1: partitions only up to yesterday because FINAL products
# typically lag 12-18 h.  The quality fallback (RAPID / RTS) handles
# dates where FINAL is not yet available.
daily_partitions = dg.DailyPartitionsDefinition(
    start_date="2020-01-01",
    end_offset=-1,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _partition_date(context: AssetExecutionContext) -> datetime.date:
    """Extract the partition date from the execution context."""
    return datetime.date.fromisoformat(context.partition_key)


def _md5_sidecar(path: Path) -> Optional[Path]:
    """Return the .md5 sidecar path if it exists next to *path*."""
    candidate = path.parent / (path.name + ".md5")
    return candidate if candidate.exists() else None


# ---------------------------------------------------------------------------
# Asset 1: gnss_product_sources
# ---------------------------------------------------------------------------

@dg.asset(
    partitions_def=daily_partitions,
    description=(
        "Load FTP source path configurations for all GNSS product types "
        "(sp3, clk, obx, erp, bias, broadcast nav) for the partition date. "
        "No FTP connections are made here — this is pure config loading from "
        "sources.yml."
    ),
)
def gnss_product_sources(context: AssetExecutionContext) -> dict:
    """
    Return ``Dict[server_name, ProductSourcesFTP]`` keyed by FTP server
    name (e.g. ``"wuhan"``, ``"cligs"``).
    """
    date = _partition_date(context)
    context.log.info(f"Loading GNSS product source configurations for {date}")
    source_map = load_product_sources_FTP(date)
    context.log.info(f"Loaded configs for servers: {list(source_map.keys())}")
    context.add_output_metadata(
        {
            "date": str(date),
            "servers": list(source_map.keys()),
            "product_types": ["sp3", "clk", "obx", "erp", "bias", "broadcast_rnx3"],
        }
    )
    return source_map


# ---------------------------------------------------------------------------
# Asset factory for sp3 / clk / obx / erp / bias
# ---------------------------------------------------------------------------

def _make_product_asset(product_attr: str, description: str) -> dg.AssetsDefinition:
    """
    Build a download-and-validate asset for a single GNSS product type.

    The asset:
    1. Calls ``download_product_with_fallback`` (Wuhan → CLIGS, FIN → RAP → RTS).
    2. Validates the downloaded file (size, gzip integrity, MD5 sidecar).
    3. Emits rich metadata (server, quality, file size, validation checks).
    4. Raises ``dg.Failure`` if download or validation fails so Dagster's
       ``RetryPolicy`` can trigger a clean retry.

    Returns
    -------
    dict
        ``{local_path, server, quality, is_valid, validation_checks,
           validation_errors}``
    """

    @dg.asset(
        name=f"downloaded_{product_attr}",
        partitions_def=daily_partitions,
        deps=[gnss_product_sources],
        description=description,
        retry_policy=dg.RetryPolicy(max_retries=3, delay=30),
    )
    def _asset(
        context: AssetExecutionContext,
        gnss_product_sources: dict,
        gnss_output: GNSSOutputResource,
    ) -> dict:
        date = _partition_date(context)
        dest_dir = gnss_output.product_dir(date)
        context.log.info(
            f"Downloading {product_attr} for {date} → {dest_dir}"
        )

        result = download_product_with_fallback(
            source_map=gnss_product_sources,
            product_attr=product_attr,
            dest_dir=dest_dir,
        )

        if result is None:
            raise dg.Failure(
                description=(
                    f"Failed to download {product_attr} for {date} "
                    "from all configured FTP sources."
                ),
                metadata={
                    "date": str(date),
                    "product": product_attr,
                    "servers_tried": ["wuhan", "cligs"],
                },
            )

        local_path, server_name, quality_label = result
        context.log.info(
            f"Downloaded {product_attr}: {local_path.name} "
            f"(server={server_name}, quality={quality_label})"
        )

        # Validate
        md5 = _md5_sidecar(local_path)
        validation = validate_product_file(local_path, md5)

        if not validation.is_valid:
            context.log.error(
                f"Validation FAILED for {local_path.name}: {validation.errors}"
            )
            # Delete corrupt file so the next retry re-downloads cleanly
            local_path.unlink(missing_ok=True)
            raise dg.Failure(
                description=(
                    f"Validation failed for {product_attr}: {validation.errors}"
                ),
                metadata={
                    "path": str(local_path),
                    "errors": str(validation.errors),
                    "checks": str(validation.checks),
                },
            )

        context.log.info(
            f"Validation PASSED for {local_path.name}: {validation.checks}"
        )
        context.add_output_metadata(
            {
                "local_path": str(local_path),
                "server": server_name,
                "quality": quality_label,
                "file_size_bytes": local_path.stat().st_size,
                "md5_sidecar_present": md5 is not None,
                "validation_checks": str(validation.checks),
            }
        )

        return {
            "local_path": str(local_path),
            "server": server_name,
            "quality": quality_label,
            "is_valid": True,
            "validation_checks": validation.checks,
            "validation_errors": [],
        }

    return _asset


# ---------------------------------------------------------------------------
# Concrete product assets (all run in parallel)
# ---------------------------------------------------------------------------

downloaded_sp3 = _make_product_asset(
    "sp3",
    "Download and validate the SP3 precise satellite orbit file "
    "(Wuhan primary, CLIGS fallback; FINAL → RAPID → RTS quality).",
)
downloaded_clk = _make_product_asset(
    "clk",
    "Download and validate the CLK precise satellite clock file.",
)
downloaded_obx = _make_product_asset(
    "obx",
    "Download and validate the OBX satellite quaternion file.",
)
downloaded_erp = _make_product_asset(
    "erp",
    "Download and validate the ERP Earth rotation parameter file.",
)
downloaded_bias = _make_product_asset(
    "bias",
    "Download and validate the code/phase bias (BIA) file.",
)


# ---------------------------------------------------------------------------
# Asset 7: downloaded_broadcast_nav
# ---------------------------------------------------------------------------

@dg.asset(
    partitions_def=daily_partitions,
    deps=[gnss_product_sources],
    description=(
        "Download and validate the broadcast navigation file. "
        "RINEX 3 multi-system file is preferred; falls back to downloading "
        "GPS + GLONASS RINEX 2 files and merging them into a BRDM file."
    ),
    retry_policy=dg.RetryPolicy(max_retries=3, delay=30),
)
def downloaded_broadcast_nav(
    context: AssetExecutionContext,
    gnss_product_sources: dict,
    gnss_output: GNSSOutputResource,
) -> dict:
    date = _partition_date(context)
    dest_dir = gnss_output.nav_dir(date)
    context.log.info(f"Downloading broadcast nav for {date} → {dest_dir}")

    result = download_broadcast_nav_with_fallback(
        source_map=gnss_product_sources,
        dest_dir=dest_dir,
    )

    if result is None:
        raise dg.Failure(
            description=(
                f"Could not download broadcast navigation for {date} "
                "from any configured FTP source "
                "(tried RINEX3 and RINEX2 fallback)."
            ),
            metadata={"date": str(date)},
        )

    local_path, server_name, format_label = result
    context.log.info(
        f"Downloaded broadcast nav: {local_path.name} "
        f"(server={server_name}, format={format_label})"
    )

    md5 = _md5_sidecar(local_path)
    validation = validate_product_file(local_path, md5)

    if not validation.is_valid:
        context.log.error(
            f"Validation FAILED for broadcast nav {local_path.name}: "
            f"{validation.errors}"
        )
        local_path.unlink(missing_ok=True)
        raise dg.Failure(
            description=f"Broadcast nav validation failed: {validation.errors}",
            metadata={
                "path": str(local_path),
                "errors": str(validation.errors),
            },
        )

    context.log.info(
        f"Validation PASSED for broadcast nav {local_path.name}: "
        f"{validation.checks}"
    )
    context.add_output_metadata(
        {
            "local_path": str(local_path),
            "server": server_name,
            "format": format_label,
            "file_size_bytes": local_path.stat().st_size,
            "validation_checks": str(validation.checks),
        }
    )

    return {
        "local_path": str(local_path),
        "server": server_name,
        "format": format_label,
        "is_valid": True,
        "validation_checks": validation.checks,
        "validation_errors": [],
    }


# ---------------------------------------------------------------------------
# Asset 8: pride_ppp_config
# ---------------------------------------------------------------------------

@dg.asset(
    partitions_def=daily_partitions,
    description=(
        "Generate the PRIDE PPP-AR configuration file from the best available "
        "validated GNSS products.  Returns the path to the written config file."
    ),
    ins={
        "downloaded_sp3": dg.AssetIn(),
        "downloaded_clk": dg.AssetIn(),
        "downloaded_obx": dg.AssetIn(),
        "downloaded_erp": dg.AssetIn(),
        "downloaded_bias": dg.AssetIn(),
        "downloaded_broadcast_nav": dg.AssetIn(),
    },
)
def pride_ppp_config(
    context: AssetExecutionContext,
    downloaded_sp3: dict,
    downloaded_clk: dict,
    downloaded_obx: dict,
    downloaded_erp: dict,
    downloaded_bias: dict,
    downloaded_broadcast_nav: dict,
    gnss_output: GNSSOutputResource,
) -> str:
    """
    Write a ``pride_ppp_ar_config`` file and return its path as a string.

    The ``SatelliteProducts`` block uses only the *filename* (not the full
    path) for each product — this is the PRIDE PPP-AR convention.
    ``Product directory`` points to ``<year>/product/`` so PRIDE resolves
    ``product/common/<filename>`` internally.
    """
    date = _partition_date(context)
    product_dir = gnss_output.product_dir(date)

    def _fname(product_dict: dict) -> Optional[str]:
        p = product_dict.get("local_path")
        return Path(p).name if p else None

    satellite_products = SatelliteProducts(
        product_directory=str(product_dir.parent),  # <year>/product/
        satellite_orbit=_fname(downloaded_sp3),
        satellite_clock=_fname(downloaded_clk),
        quaternions=_fname(downloaded_obx),
        erp=_fname(downloaded_erp),
        code_phase_bias=_fname(downloaded_bias),
    )

    # Prefer the installed PRIDE default template; fall back to built-in defaults
    try:
        config = PRIDEPPPFileConfig.load_default()
        context.log.info("Loaded PRIDE PPP-AR default config template.")
    except FileNotFoundError:
        context.log.warning(
            "PRIDE PPP-AR config_template not found — using built-in defaults. "
            "Install PRIDE-PPPAR to use the official template."
        )
        config = PRIDEPPPFileConfig(
            observation=ObservationConfig(table_directory="Default"),
            satellite_products=satellite_products,
        )

    config.satellite_products = satellite_products

    config_path = gnss_output.config_file_path(date)
    config.write_config_file(config_path)
    context.log.info(f"Wrote PRIDE PPP-AR config → {config_path}")

    context.add_output_metadata(
        {
            "config_path": str(config_path),
            "product_directory": str(product_dir.parent),
            "sp3": _fname(downloaded_sp3),
            "clk": _fname(downloaded_clk),
            "obx": _fname(downloaded_obx),
            "erp": _fname(downloaded_erp),
            "bias": _fname(downloaded_bias),
            "broadcast_nav": _fname(downloaded_broadcast_nav),
            "quality_sp3": downloaded_sp3.get("quality"),
            "quality_clk": downloaded_clk.get("quality"),
            "quality_obx": downloaded_obx.get("quality"),
            "quality_erp": downloaded_erp.get("quality"),
            "quality_bias": downloaded_bias.get("quality"),
        }
    )

    return str(config_path)


# ---------------------------------------------------------------------------
# Module-level asset list for definitions.py
# ---------------------------------------------------------------------------

all_assets: list[dg.AssetsDefinition] = [
    gnss_product_sources,
    downloaded_sp3,
    downloaded_clk,
    downloaded_obx,
    downloaded_erp,
    downloaded_bias,
    downloaded_broadcast_nav,
    pride_ppp_config,
]
