"""
GNSS product download and management operations.

Uses the ``gnss-ppp-products`` Tasks SDK to declaratively resolve and
download orbit, clock, bias, ERP, OBX, and navigation products from
multiple IGS data centers.

Legacy functions (``get_gnss_products``, ``get_nav_file``) are preserved
as the public API but now delegate to :func:`task_config.build_task`.
"""

import datetime
import gzip
import logging
from pathlib import Path
from typing import Dict, Optional

from gnss_ppp_products.tasks import DependencyType, Task, TaskResult
from gnss_ppp_products.assets.base.igs_conventions import ProductFileFormat

from .config import PRIDEPPPFileConfig, SatelliteProducts
from .rinex import rinex_get_time_range
from .task_config import build_task

logger = logging.getLogger(__name__)
# ---------------------------------------------------------------------------
# Format→SatelliteProducts field mapping
# ---------------------------------------------------------------------------

_FORMAT_TO_PRODUCT_FIELD: Dict[ProductFileFormat, str] = {
    ProductFileFormat.SP3: "satellite_orbit",
    ProductFileFormat.CLK: "satellite_clock",
    ProductFileFormat.BIA: "code_phase_bias",
    ProductFileFormat.OBX: "quaternions",
    ProductFileFormat.ERP: "erp",
}


def uncompress_file(file_path: Path, dest_dir: Optional[Path] = None) -> Optional[Path]:
    """Decompress a gzip file and return the path of the decompressed file.

    Parameters
    ----------
    file_path : Path
        The path of the compressed file.
    dest_dir : Path, optional
        Destination directory for the decompressed file.

    Returns
    -------
    Path or None
        The path of the decompressed file, or None on failure.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File {file_path} does not exist.")

    out_file_path = file_path.with_suffix("")
    if dest_dir is not None:
        out_file_path = dest_dir / out_file_path.name
        if not dest_dir.exists():
            dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        with gzip.open(file_path, "rb") as f_in:
            with open(out_file_path, "wb") as f_out:
                f_out.write(f_in.read())
    except EOFError as e:
        logger.error(f"Failed to decompress {file_path}: {e}")
        file_path.unlink(missing_ok=True)
        return None
    file_path.unlink(missing_ok=True)
    return out_file_path


# ---------------------------------------------------------------------------
# Extracting discovered product filenames into SatelliteProducts
# ---------------------------------------------------------------------------


def _result_to_product_status(result: TaskResult) -> Dict[str, str]:
    """Map a TaskResult to ``{field_name: filename}`` for SatelliteProducts.

    Iterates over resolved products, decompresses ``.gz`` files in place,
    and returns the first available filename for each product format.
    """
    product_status: Dict[str, str] = {}

    for rp in result.fulfilled:
        # Only product-type dependencies map to SatelliteProducts fields
        if rp.dependency_type != DependencyType.PRODUCTS:
            continue

        fmt = getattr(rp.query, "format", None)
        if fmt not in _FORMAT_TO_PRODUCT_FIELD:
            continue

        field = _FORMAT_TO_PRODUCT_FIELD[fmt]
        if field in product_status:
            continue  # first match wins

        # Pick the file path (local or downloaded)
        path: Optional[Path] = None
        if rp.found_locally and rp.local_paths:
            path = rp.local_paths[0]
        elif rp.downloaded_path is not None:
            path = rp.downloaded_path

        if path is None:
            continue

        # Decompress if needed
        if path.suffix == ".gz" and path.exists():
            decompressed = uncompress_file(path, path.parent)
            if decompressed is not None:
                path = decompressed

        product_status[field] = path.name

    return product_status


# ---------------------------------------------------------------------------
# Public API — get_nav_file
# ---------------------------------------------------------------------------


def get_nav_file(
    rinex_path: Path,
    pride_dir: Path,
    override: bool = False,
) -> Optional[Path]:
    """Build or locate a navigation file for a given RINEX file.

    Uses the Tasks SDK to search locally and download from remote
    centers if not found.

    Parameters
    ----------
    rinex_path : Path
        The path to the RINEX observation file.
    pride_dir : Path
        Root directory for PRIDE products (used as local storage root).
    override : bool
        If True, re-download even if a nav file already exists.

    Returns
    -------
    Path or None
        The path to a navigation file, or None on failure.
    """
    start_date, _ = rinex_get_time_range(rinex_path)
    if start_date is None:
        logger.error("No TIME OF FIRST OBS found in RINEX file.")
        return None

    nav_date = start_date.date() if isinstance(start_date, datetime.datetime) else start_date

    task = build_task(
        local_storage_root=pride_dir,
    )

    # Only resolve RINEX dependency
    from gnss_ppp_products.tasks import ProductDependency
    task.dependencies = [ProductDependency(type=DependencyType.RINEX, required=True)]

    result = task.resolve(date=nav_date)

    # If found locally and not overriding, return the first match
    if not override and result.found:
        path = result.found[0].local_paths[0]
        if path.exists() and path.stat().st_size > 0:
            logger.debug(f"Navigation file found locally: {path}")
            return path

    # Download missing
    task.download(result)

    for rp in result.fulfilled:
        path = None
        if rp.found_locally and rp.local_paths:
            path = rp.local_paths[0]
        elif rp.downloaded_path is not None:
            path = rp.downloaded_path
        if path is not None and path.exists():
            logger.info(f"Navigation file resolved: {path}")
            return path

    logger.error("Failed to build or locate navigation file")
    return None


# ---------------------------------------------------------------------------
# Public API — get_gnss_products
# ---------------------------------------------------------------------------


def get_gnss_products(
    rinex_path: Optional[Path],
    pride_dir: Path,
    override: bool = False,
    date: Optional[datetime.date | datetime.datetime] = None,
    override_config: bool = True,
) -> Optional[Path]:
    """Generate or retrieve GNSS products for a given RINEX file or date.

    Uses the Tasks SDK to resolve products locally first, then
    downloads anything missing from configured analysis centers.

    Returns the path to a PRIDE config file that catalogs the products.

    Parameters
    ----------
    rinex_path : Path or None
        The path to the RINEX file. If provided, date is extracted from it.
    pride_dir : Path
        The directory where the PRIDE products are stored.
    override : bool
        If True, re-download products even if they already exist.
    date : datetime.date or datetime.datetime, optional
        The date for which to retrieve products. Used when rinex_path
        is None.
    override_config : bool
        If True, re-download products even if a config file already exists.

    Returns
    -------
    Path or None
        The path to the config file, or None on failure.
    """
    start_date: Optional[datetime.date] = None

    if rinex_path is not None:
        ts_start, _ = rinex_get_time_range(rinex_path)
        if ts_start is None:
            logger.error("No TIME OF FIRST OBS found in RINEX file.")
            return None
        start_date = ts_start.date() if isinstance(ts_start, datetime.datetime) else ts_start
    elif date is not None:
        if isinstance(date, datetime.datetime):
            start_date = date.date()
        elif isinstance(date, datetime.date):
            start_date = date
        else:
            raise TypeError(
                f"Invalid date type {type(date)}. Must be datetime.date or datetime.datetime"
            )
    else:
        raise ValueError("Either rinex_path or date must be provided")

    # ---------------------------------------------------------------
    # Build and execute the Task
    # ---------------------------------------------------------------

    task: Task = build_task(
        local_storage_root=pride_dir,
    )

    result: TaskResult = task.resolve(date=start_date)

    logger.info(result.summary())

    # ---------------------------------------------------------------
    # Map results → SatelliteProducts → config file
    # ---------------------------------------------------------------

    product_status = _result_to_product_status(result)

    # Determine product directory from the first resolved product
    product_dir: Optional[Path] = None
    for rp in result.fulfilled:
        if rp.local_paths:
            product_dir = rp.local_paths[0].parent
            break
        if rp.downloaded_path is not None:
            product_dir = rp.downloaded_path.parent
            break

    satellite_products = SatelliteProducts(
        satellite_orbit=product_status.get("satellite_orbit"),
        satellite_clock=product_status.get("satellite_clock"),
        code_phase_bias=product_status.get("code_phase_bias"),
        quaternions=product_status.get("quaternions"),
        erp=product_status.get("erp"),
        product_directory=str(product_dir) if product_dir else str(pride_dir),
    )
    config_template = PRIDEPPPFileConfig.load_default()
    config_template.satellite_products = satellite_products

    daily_config_dir = pride_dir / str(start_date.year) / f"{start_date.timetuple().tm_yday:03d}"
    daily_config_dir.mkdir(parents=True, exist_ok=True)
    daily_config_path = daily_config_dir / "config_file"
    config_template.write_config_file(daily_config_path)
    return daily_config_path
