"""
Troposphere Products Resources
==============================

This module provides FTP/HTTP resources for downloading tropospheric correction
products used in GNSS Precise Point Positioning (PPP):

    - **VMF** (Vienna Mapping Functions): Troposphere mapping and delay coefficients

Product Categories
------------------
These products provide:
    - Hydrostatic and wet mapping function coefficients
    - Zenith hydrostatic and wet delay values
    - Used for precise tropospheric modeling in PPP

Servers
-------
    - VMF Data Server (vmf.geo.tuwien.ac.at): VMF1/VMF3 grid products
"""

import datetime
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel
import requests

from .base import ResourceQueryResult, DownloadProtocol
from .http_servers import VMF_HTTP
from .utils import _parse_date

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums and Data Classes
# ---------------------------------------------------------------------------


class AtmosphericProductQuality(str, Enum):
    """Quality levels for atmospheric products."""
    
    FINAL = "final"
    RAPID = "rapid"
    PREDICTED = "predicted"


@dataclass
class AtmosphericFileResult(ResourceQueryResult):
    """
    Result of a successful atmospheric product query.

    Attributes
    ----------
    server : str
        Server URL (FTP or HTTP).
    directory : str
        Remote directory path.
    filename : str
        Remote filename.
    protocol : DownloadProtocol
        Protocol for downloading (FTP, FTPS, HTTP, HTTPS).
    product_type : str
        Product type identifier (vmf1, vmf3).
    quality : AtmosphericProductQuality
        Quality level at which the file was found.
    """

    product_type: str = ""
    quality: AtmosphericProductQuality = AtmosphericProductQuality.FINAL


# ---------------------------------------------------------------------------
# VMF Products (Vienna Mapping Functions)
# ---------------------------------------------------------------------------


class VMFFileRegex(BaseModel):
    """
    Regex patterns for VMF grid products.
    
    File naming conventions:
        - VMF1: VMFG_{year}{doy}.H{hour}  (6-hourly grids at 00, 06, 12, 18)
        - VMF3: VMF3_{year}{doy}.H{hour}
        
    For daily aggregates, match any hour or use combined files.
    """

    regex: str = "{product}_{year}{month}{day}.{hh}"
    
    def query(self, date: datetime.date, product: Literal["VMF1", "VMF3"] = "VMF1", hour: Literal['H00', 'H06', 'H12', 'H18'] = 'H00') -> str:
        """Return regex for specified product and date."""
        year, doy = _parse_date(date)
        month = str(date.month).zfill(2)
        day = str(date.day).zfill(2)
        match product:
            case "VMF1":
                product = "VMFG"
            case _:
                pass
        return self.regex.format(product=product.upper(), year=year, month=month, day=day, hh=hour)


class VMFHTTPProductSource(BaseModel):
    """
    HTTP source for Vienna Mapping Functions (VMF) troposphere products.
    
    VMF products provide:
        - Hydrostatic and wet mapping function coefficients
        - Zenith hydrostatic and wet delay values
        - Used for precise tropospheric modeling in PPP
    
    Example
    -------
    >>> source = VMFHTTPProductSource()
    >>> result = source.query_vmf1(datetime.date(2025, 1, 1))
    >>> print(result.url)
    https://vmf.geo.tuwien.ac.at/trop_products/GRID/VMF1/VMF1_OP/2025/VMFG_2025001.H00
    """
    
    # directory_source: VMFDirectorySource = VMFDirectorySource()
    file_regex: VMFFileRegex = VMFFileRegex()
    http_server: str = VMF_HTTP
    archive_dir: str = "trop_products/GRID/{resolution}/{product}/{product}_OP/{year}"
    
    def query(self, date: datetime.date, resolution: Literal["1x1", "2.5x2","5x5"] = "1x1", product: Literal["VMF1", "VMF3"] = "VMF3", hour: Literal['H00', 'H06', 'H12', 'H18'] = 'H00') -> Optional[AtmosphericFileResult]:
        """
        Query for a VMF product file.
        
        Parameters
        ----------
        date : datetime.date
            Date for which to retrieve the VMF product.
        resolution : str
            Grid resolution ("1x1", "2.5x2", "5x5").
        product : str
            Either "vmf1" or "vmf3".
        hour : int, optional
            Specific hour (0, 6, 12, 18). If None, returns first available.
            
        Returns
        -------
        AtmosphericFileResult or None
            File result if found.
        """
        if product not in ["VMF1", "VMF3"]:
            raise ValueError("Product must be either 'VMF1' or 'VMF3'")
        match resolution:
            case "1x1":
                if product != "VMF3":
                    raise ValueError("Only VMF3 is available at 1x1 resolution")
            case "2.5x2":
                if product != "VMF1":
                    raise ValueError("Only VMF1 is available at 2.5x2 resolution")
            case "5x5":
                if product != "VMF3":
                    raise ValueError("Only VMF3 is available at 5x5 resolution")
            case _:
                raise ValueError(f"Unsupported resolution: {resolution}")
        
        match product:
            case "VMF1":
                if date.year < 1985:
                    raise ValueError("VMF1 products are only available from 1985 onwards")
            case "VMF3":
                if date.year < 2008:
                    raise ValueError("VMF3 products are only available from 2008 onwards")

        year,doy = _parse_date(date)

        directory = self.archive_dir.format(resolution=resolution, product=product.upper(), year=year)
        
        filename = self.file_regex.query(date=date, product=product, hour=hour)

        full_url = f"{self.http_server.rstrip('/')}/{directory.strip('/')}/{filename}"
        
        try:
            response = requests.head(full_url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Failed to retrieve VMF file: {e}")
            return None
        return AtmosphericFileResult(
            server=self.http_server,
            directory=directory,
            filename=filename,
            protocol=DownloadProtocol.HTTPS,
            product_type=product.lower(),
            quality=AtmosphericProductQuality.FINAL,
        )
    
