"""
Orography Products Resources
============================

This module provides HTTP resources for downloading orography (terrain height)
files used in GNSS Precise Point Positioning (PPP) tropospheric modeling.

Orography files provide ellipsoidal surface heights at grid points, which are
required for:
    - VMF (Vienna Mapping Functions) troposphere corrections
    - Station height interpolation for grid-based troposphere products

Product Categories
------------------
    - **orography_ell**: Ellipsoidal orography grids for VMF interpolation

Servers
-------
    - VMF Data Server (vmf.geo.tuwien.ac.at): Orography grid files
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel
import requests

from .base import ResourceQueryResult, DownloadProtocol


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums and Data Classes
# ---------------------------------------------------------------------------


class OrographyGridResolution(str, Enum):
    """Grid resolution options for orography files."""
    
    ONE_BY_ONE = "1x1"
    FIVE_BY_FIVE = "5x5"


@dataclass
class OrographyFileResult(ResourceQueryResult):
    """
    Result of a successful orography file query.

    Attributes
    ----------
    server : str
        Server URL (HTTP/HTTPS).
    directory : str
        Remote directory path.
    filename : str
        Remote filename.
    protocol : DownloadProtocol
        Protocol for downloading (HTTP, HTTPS).
    resolution : OrographyGridResolution
        Grid resolution of the orography file.
    """

    resolution: OrographyGridResolution = OrographyGridResolution.ONE_BY_ONE


# ---------------------------------------------------------------------------
# VMF Orography Products (Vienna Mapping Functions)
# ---------------------------------------------------------------------------


class VMFOrographyHTTPSource(BaseModel):
    """
    HTTP source for VMF orography (terrain height) grid files.
    
    Orography files provide ellipsoidal surface heights at grid points,
    required for interpolating VMF troposphere corrections to station locations.
    
    Available resolutions:
        - 1x1: 1-degree grid (orography_ell_1x1)
        - 5x5: 5-degree grid (orography_ell_5x5)
    
    Example
    -------
    >>> source = VMFOrographyHTTPSource()
    >>> result = source.query(resolution="1x1")
    >>> print(result.url)
    https://vmf.geo.tuwien.ac.at/station_coord_files/orography_ell_1x1
    """
    
    http_server: str = "https://vmf.geo.tuwien.ac.at"
    directory: str = "station_coord_files"
    filename_pattern: str = "orography_ell_{resolution}"
    
    def query(
        self, 
        resolution: Literal["1x1", "5x5"] = "1x1"
    ) -> Optional[OrographyFileResult]:
        """
        Query for an orography grid file.
        
        Parameters
        ----------
        resolution : str
            Grid resolution ("1x1" or "5x5").
            
        Returns
        -------
        OrographyFileResult or None
            File result if found, None if the request fails.
            
        Raises
        ------
        ValueError
            If an unsupported grid resolution is provided.
        """
        if resolution not in ("1x1", "5x5"):
            raise ValueError(f"Unsupported grid resolution: {resolution}")
        
        filename = self.filename_pattern.format(resolution=resolution)
        full_url = f"{self.http_server.rstrip('/')}/{self.directory.strip('/')}/{filename}"
        
        try:
            response = requests.head(full_url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Failed to retrieve orography file: {e}")
            return None
        
        resolution_enum = (
            OrographyGridResolution.ONE_BY_ONE 
            if resolution == "1x1" 
            else OrographyGridResolution.FIVE_BY_FIVE
        )
        
        return OrographyFileResult(
            server=self.http_server,
            directory=self.directory,
            filename=filename,
            protocol=DownloadProtocol.HTTPS,
            resolution=resolution_enum,
        )
