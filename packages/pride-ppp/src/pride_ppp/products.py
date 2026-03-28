"""Author: Franklyn Dunbar

GNSS product resolution and PRIDE config file generation.

Uses ``gnss-ppp-products`` dependency resolution to discover and download
orbit, clock, bias, ERP, OBX, navigation, and reference products from
multiple IGS analysis centers, then writes a PRIDE PPP-AR ``config_file``
that points to the resolved files on disk.
"""

from __future__ import annotations

import datetime
import logging
from pathlib import Path
from typing import Dict, Optional

from gnss_ppp_products import (
    DependencyResolver,
    ProductEnvironment,
    QueryFactory,
    ResourceFetcher,
    WorkSpace,
)
from .defaults import (
    DefaultProductEnvironment,
    DefaultWorkSpace,
    Pride_PPP_task,
)
from gnss_ppp_products.specifications.dependencies.dependencies import (
    DependencyResolution,
    DependencySpec,
)

from .config import PRIDEPPPFileConfig, SatelliteProducts
from .rinex import rinex_get_time_range

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Spec name → SatelliteProducts field mapping
# ---------------------------------------------------------------------------

_SPEC_TO_PRODUCT_FIELD: Dict[str, str] = {
    "ORBIT": "satellite_orbit",
    "CLOCK": "satellite_clock",
    "BIA": "code_phase_bias",
    "ATTOBX": "quaternions",
    "ERP": "erp",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_resolver(
    pride_dir: Path,
    dep_spec: Optional[DependencySpec] = None,
    env: Optional[ProductEnvironment] = None,
    workspace: Optional[WorkSpace] = None,
) -> tuple[DependencyResolver, WorkSpace]:
    """Construct a :class:`DependencyResolver` wired to default or custom configs.

    Args:
        pride_dir: Root directory for local PRIDE product storage.
        dep_spec: Override dependency specification.
        env: Override product environment.
        workspace: Override workspace.

    Returns:
        A tuple of (resolver, workspace).
    """
    if env is None:
        env = DefaultProductEnvironment
    if workspace is None:
        workspace = DefaultWorkSpace
    if dep_spec is None:
        dep_spec = Pride_PPP_task

    if "pride_config" not in workspace._registered_specs:
        workspace.register_spec(
            base_dir=pride_dir, spec_ids=["pride_config"], alias="pride"
        )

    qf = QueryFactory(product_environment=env, workspace=workspace)
    fetcher = ResourceFetcher(max_connections=10)

    resolver = DependencyResolver(
        dep_spec=dep_spec,
        product_environment=env,
        query_factory=qf,
        fetcher=fetcher,
    )
    return resolver, workspace

def _resolution_to_table_dir(resolution: DependencyResolution) -> Optional[Path]:
    """Extract the common parent directory of resolved products, if any.

    Args:
        resolution: The completed dependency resolution.
    Returns:
        The table directory.
    """
    for rd in resolution.fulfilled:
        if rd.spec in "ATTATX":
            path = rd.local_path
            if path is not None:
                return path.parent


def _resolution_to_satellite_products(
    resolution: DependencyResolution,
) -> tuple[SatelliteProducts, Optional[Path]]:
    """Map a :class:`DependencyResolution` to :class:`SatelliteProducts`.

    Args:
        resolution: The completed dependency resolution.

    Returns:
        A tuple of (SatelliteProducts, product_directory).
    """
    product_status: Dict[str, str] = {}
    product_dir: Optional[Path] = None

    for rd in resolution.fulfilled:
        field = _SPEC_TO_PRODUCT_FIELD.get(rd.spec)
        if field is None or field in product_status:
            continue

        path = rd.local_path
        if path is None:
            continue

        product_status[field] = path.name
        if product_dir is None:
            product_dir = path.parent

    return (
        SatelliteProducts(
            satellite_orbit=product_status.get("satellite_orbit"),
            satellite_clock=product_status.get("satellite_clock"),
            code_phase_bias=product_status.get("code_phase_bias"),
            quaternions=product_status.get("quaternions"),
            erp=product_status.get("erp"),
            product_directory=str(product_dir) if product_dir else "Default",
        ),
        product_dir,
    )


def _write_pride_config(
    satellite_products: SatelliteProducts,
    table_dir: Optional[Path],
    pride_dir: Path,
    start_date: datetime.date,
) -> Path:
    """Write a PRIDE config file populated with resolved product paths.

    Args:
        satellite_products: Resolved satellite product filenames.
        pride_dir: Root PRIDE directory.
        start_date: Processing date (used for directory layout).

    Returns:
        Path to the written config file.
    """
    config = PRIDEPPPFileConfig.load_default()
    config.satellite_products = satellite_products
    config.observation.table_directory = str(table_dir) if table_dir else "Default"

    daily_dir = (
        pride_dir / str(start_date.year) / f"{start_date.timetuple().tm_yday:03d}"
    )
    daily_dir.mkdir(parents=True, exist_ok=True)
    config_path = daily_dir / "config_file"
    config.write_config_file(config_path)
    return config_path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_products(
    date: datetime.date | datetime.datetime,
    pride_dir: Path,
    *,
    dep_spec: Optional[DependencySpec] = None,
    env: Optional[ProductEnvironment] = None,
    workspace: Optional[WorkSpace] = None,
    local_sink_id: str = "pride",
    station: Optional[str] = None,
) -> DependencyResolution:
    """Resolve all PRIDE PPP dependencies for a given date.

    This is the lower-level API that returns the raw resolution result
    without generating a config file.

    Args:
        date: Target date for product resolution.
        pride_dir: Root directory for local PRIDE product storage.
        dep_spec: Override dependency specification.
        env: Override product environment.
        workspace: Override workspace.
        local_sink_id: Local resource identifier (default ``'pride'``).
        station: Optional station identifier for lockfile scoping.

    Returns:
        The :class:`DependencyResolution` with all resolved products.
    """
    if isinstance(date, datetime.date) and not isinstance(date, datetime.datetime):
        date = datetime.datetime(
            date.year, date.month, date.day, tzinfo=datetime.timezone.utc
        )
    elif date.tzinfo is None:
        date = date.replace(tzinfo=datetime.timezone.utc)

    resolver, _ = _build_resolver(
        pride_dir=pride_dir, dep_spec=dep_spec, env=env, workspace=workspace
    )

    resolution, _ = resolver.resolve(
        date=date, local_sink_id=local_sink_id, station=station
    )
    return resolution


def get_gnss_products(
    rinex_path: Optional[Path] = None,
    pride_dir: Optional[Path] = None,
    *,
    date: Optional[datetime.date | datetime.datetime] = None,
    override: bool = False,
    local_sink_id: str = "pride",
    station: Optional[str] = None,
) -> Optional[Path]:
    """Resolve GNSS products and generate a PRIDE config file.

    Uses ``gnss-ppp-products`` dependency resolution to find or download
    orbit, clock, bias, ERP, OBX, navigation, and reference products,
    then writes a PRIDE PPP ``config_file`` pointing to them.

    Args:
        rinex_path: Path to a RINEX file (date extracted from header).
        pride_dir: Root directory for PRIDE product storage.
        date: Explicit processing date (used when *rinex_path* is ``None``).
        override: If ``True``, re-resolve even if products exist locally.
        local_sink_id: Local resource identifier (default ``'pride'``).
        station: Optional station identifier for lockfile scoping.

    Returns:
        Path to the generated PRIDE config file, or ``None`` on failure.

    Raises:
        ValueError: If neither *rinex_path* nor *date* is provided.
        TypeError: If *date* has an unsupported type.
    """
    if pride_dir is None:
        raise ValueError("pride_dir must be provided")

    # Determine the processing date
    start_date: Optional[datetime.date] = None

    if rinex_path is not None:
        ts_start, _ = rinex_get_time_range(rinex_path)
        if ts_start is None:
            logger.error("No TIME OF FIRST OBS found in RINEX file.")
            return None
        start_date = (
            ts_start.date() if isinstance(ts_start, datetime.datetime) else ts_start
        )
    elif date is not None:
        if isinstance(date, datetime.datetime):
            start_date = date.date()
        elif isinstance(date, datetime.date):
            start_date = date
        else:
            raise TypeError(
                f"Invalid date type {type(date)}. "
                "Must be datetime.date or datetime.datetime."
            )
    else:
        raise ValueError("Either rinex_path or date must be provided.")

    # Resolve dependencies
    resolution = resolve_products(
        date=start_date,
        pride_dir=pride_dir,
        local_sink_id=local_sink_id,
        station=station,
    )

    logger.info(resolution.summary())

    if not resolution.all_required_fulfilled:
        logger.error(
            f"Not all required products resolved: "
            f"{[r.spec for r in resolution.missing if r.required]}"
        )

    # Map resolved products → SatelliteProducts → config file
    satellite_products, _ = _resolution_to_satellite_products(resolution)
    table_dir = _resolution_to_table_dir(resolution)
    config_path = _write_pride_config(satellite_products, table_dir,pride_dir, start_date)
    logger.info(f"PRIDE config written to {config_path}")
    return config_path
