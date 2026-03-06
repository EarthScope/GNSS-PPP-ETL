"""
Atmospheric Products FTP Resources
==================================

This module provides FTP resources for downloading atmospheric correction products
used in GNSS Precise Point Positioning (PPP):

    - **GIM** (Global Ionosphere Maps): VTEC grids for ionospheric correction
    - **VMF** (Vienna Mapping Functions): Troposphere mapping and delay coefficients

Product Categories
------------------
These are distinct from orbit/clock products in that they:
    - Provide correction models rather than satellite states
    - May have different quality tiers (FINAL, RAPID, PREDICTED)
    - Often use different FTP servers than orbit/clock products

Servers
-------
    - CODE (ftp.aiub.unibe.ch): GIM products in IONEX format
    - VMF Data Server (vmf.geo.tuwien.ac.at): VMF1/VMF3 grid products
"""

import datetime
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel
import requests

from .utils import (
    _parse_date,
    ftp_list_directory,
    find_best_match_in_listing,
)

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
class AtmosphericFileResult:
    """
    Result of a successful atmospheric product FTP query.

    Attributes
    ----------
    ftpserver : str
        FTP host URL, e.g. ``ftp://ftp.aiub.unibe.ch``.
    directory : str
        Remote directory path.
    filename : str
        Remote filename.
    product_type : str
        Product type identifier (gim, vmf1, vmf3).
    quality : AtmosphericProductQuality
        Quality level at which the file was found.
    """

    ftpserver: str
    directory: str
    filename: str
    product_type: str
    quality: AtmosphericProductQuality

    @property
    def url(self) -> str:
        """Full FTP URL to the remote file."""
        host = self.ftpserver.rstrip("/")
        path = self.directory.strip("/")
        return f"{host}/{path}/{self.filename}"


# ---------------------------------------------------------------------------
# VMF Products (Vienna Mapping Functions)
# ---------------------------------------------------------------------------


class VMFDirectorySource(BaseModel):
    """
    Directory structure for VMF (Vienna Mapping Functions) products.
    
    Products available:
        - VMF1: Vienna Mapping Function 1 (operational grids)
        - VMF3: Vienna Mapping Function 3 (operational grids)
        
    Server: vmf.geo.tuwien.ac.at (or mirrors)
    
    Directory structure:
        trop_products/GRID/VMF1/VMF1_OP/{year}/
        trop_products/GRID/VMF3/VMF3_OP/{year}/
    """
    
    http_server:str = "https://vmf.geo.tuwien.ac.at/"
    vmf1_path: str = "trop_products/GRID/VMF1/VMF1_OP/{year}"
    vmf3_path: str = "trop_products/GRID/VMF3/VMF3_OP/{year}"
    
    def vmf1_directory(self, date: datetime.date) -> str:
        """Return VMF1 directory for a given date."""
        year, _ = _parse_date(date)
        return self.vmf1_path.format(year=year)
    
    def vmf3_directory(self, date: datetime.date) -> str:
        """Return VMF3 directory for a given date."""
        year, _ = _parse_date(date)
        return self.vmf3_path.format(year=year)


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
    http_server: str = "https://vmf.geo.tuwien.ac.at/"
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
        assert product in ["VMF1", "VMF3"], "Product must be either 'VMF1' or 'VMF3'"
        match resolution:
            case "1x1":
                assert product == "VMF3", "Only VMF3 is available at 1x1 resolution"
            case "2.5x2":
                assert product == "VMF1", "Only VMF1 is available at 2.5x2 resolution"
            case "5x5":
                assert product == "VMF3", "Only VMF3 is available at 5x5 resolution"
            case _:
                raise ValueError(f"Unsupported resolution: {resolution}")
            
        year,doy = _parse_date(date)

        directory = self.archive_dir.format(resolution=resolution, product=product.upper(), year=year)
        
        filename = self.file_regex.query(date=date, product=product, hour=hour)

        full_url = f"{self.http_server.rstrip('/')}/{directory.strip('/')}/{filename}"
        
        try:
            response = requests.head(full_url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Failed to retrieve ANTEX file from NGS/NOAA: {e}")
            return None
        return AtmosphericFileResult(
            ftpserver=self.http_server,
            directory=directory,
            filename=filename,
            product_type=product.lower(),
            quality=AtmosphericProductQuality.FINAL,  # VMF products are typically final quality
        )
    
