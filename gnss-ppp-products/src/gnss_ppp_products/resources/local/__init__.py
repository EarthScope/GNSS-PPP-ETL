"""
Local GNSS Product Resources
============================

Provides a structured local folder system for downloaded GNSS products,
using the same query interface as remote resources.

Directory Strategies
--------------------
    - **PRIDE**: ``{year}/{doy}/`` for daily, ``{year}/product/common/`` for common
    - **GPS_WEEK**: ``{gps_week}/``
    - **YEAR_DOY**: ``{year}/{doy}/``
    - **YEAR_MONTH**: ``{year}/{month:02d}/``

Quick Start
-----------
    >>> from gnss_ppp_products.resources.local import LocalProductStore
    >>> store = LocalProductStore("/data/gnss")
    >>> 
    >>> # Query for products (returns None if not found)
    >>> orbit = store.query_orbit(datetime.date(2025, 1, 15))
    >>> nav = store.query_navigation(datetime.date(2025, 1, 15))
    >>> antex = store.query_antex(datetime.date(2025, 1, 15))
    >>>
    >>> # Check existence
    >>> if orbit and orbit.exists:
    ...     print(f"Found: {orbit.path}")
    >>>
    >>> # Ensure directories exist before downloading
    >>> dirs = store.ensure_directories(datetime.date(2025, 1, 15))

Integration with Remote Resources
---------------------------------
The local sources mirror the remote query interface, enabling unified workflows::

    from gnss_ppp_products.resources import IGSAntexHTTP
    from gnss_ppp_products.resources.local import LocalProductStore

    # Check local first, download if missing
    store = LocalProductStore("/data/gnss")
    result = store.query_antex(date)
    
    if not result or not result.exists:
        remote = IGSAntexHTTP()
        remote_result = remote.query(date)
        # Download and save to store.dir_builder.static_dir()
"""

from .base import (
    DirectoryStrategy,
    LocalDirectoryBuilder,
    LocalFileFinder,
    LocalFileResult,
    LocalOrbitClockResult,
    LocalNavigationResult,
    LocalAntexResult,
    LocalAtmosphericResult,
    LocalProductSource,
    ProductCategory,
)

from .sources import (
    LocalOrbitClockSource,
    LocalNavigationSource,
    LocalAntexSource,
    LocalAtmosphericSource,
    LocalProductStore,
)

__all__ = [
    # Strategy/Category enums
    "DirectoryStrategy",
    "ProductCategory",
    # Base classes
    "LocalDirectoryBuilder",
    "LocalFileFinder",
    "LocalFileResult",
    "LocalProductSource",
    # Result types
    "LocalOrbitClockResult",
    "LocalNavigationResult",
    "LocalAntexResult",
    "LocalAtmosphericResult",
    # Product sources
    "LocalOrbitClockSource",
    "LocalNavigationSource",
    "LocalAntexSource",
    "LocalAtmosphericSource",
    # Unified store
    "LocalProductStore",
]
