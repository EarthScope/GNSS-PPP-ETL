"""
Local GNSS Product Resources
============================

Provides a structured local folder system for downloaded GNSS products,
using the same query interface as remote resources.

Directory Strategies
--------------------
    - **GPS_WEEK**: ``{year}/{gps_week}/{doy}/`` for daily
    - **PRIDE**: ``{year}/{doy}/`` for daily, ``{year}/product/common/`` for common

Quick Start
-----------
    >>> from gnss_ppp_products.resources.local import LocalDataSource, PrideDataSource
    >>> 
    >>> # Generic GPS week-based structure
    >>> source = LocalDataSource("/data/gnss")
    >>> daily_dir = source.gps_week_day_directory(datetime.date(2025, 1, 15))
    >>>
    >>> # PRIDE PPP-AR structure
    >>> pride = PrideDataSource("/data/pride", "/data/pride/table")
    >>> common_dir = pride.common_product_directory(datetime.date(2025, 1, 15))
    >>> doy_dir = pride.doy_directory(datetime.date(2025, 1, 15))

Integration with Remote Resources
---------------------------------
The local sources mirror the remote query interface, enabling unified workflows::

    from gnss_ppp_products.resources import IGSAntexHTTP
    from gnss_ppp_products.resources.local import LocalDataSource

    # Check local first, download if missing
    source = LocalDataSource("/data/gnss")
    result = source.query(date, temporal_coverage, regex)
    
    if result is None:
        remote = IGSAntexHTTP()
        remote_result = remote.query(date)
        # Download to appropriate directory
"""

from .base import (
    # Enums
    DirectoryStrategy,
    ProductCategory,
    # Temporal utilities
    _parse_date,
    _date_to_gps_week,
    _date_to_gps_week_day,
    _date_to_year_doy,
    # Result types
    LocalFileResult,
    LocalOrbitClockResult,
    LocalNavigationResult,
    LocalAntexResult,
    LocalAtmosphericResult,
    # Builders
    LocalDirectoryBuilder,
    LocalFileFinder,
    LocalProductSource,
)

from .sources import (
    LocalDataSource,
    PrideDataSource,
)

__all__ = [
    # Strategy/Category enums
    "DirectoryStrategy",
    "ProductCategory",
    # Temporal utilities  
    "_parse_date",
    "_date_to_gps_week",
    "_date_to_gps_week_day",
    "_date_to_year_doy",
    # Result types
    "LocalFileResult",
    "LocalOrbitClockResult",
    "LocalNavigationResult",
    "LocalAntexResult",
    "LocalAtmosphericResult",
    # Builders
    "LocalDirectoryBuilder",
    "LocalFileFinder",
    "LocalProductSource",
    # Data sources
    "LocalDataSource",
    "PrideDataSource",
]
