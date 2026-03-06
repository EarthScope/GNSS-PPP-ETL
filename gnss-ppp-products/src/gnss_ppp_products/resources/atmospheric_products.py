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
from dataclasses import dataclass
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel

from .utils import (
    _parse_date,
    ftp_list_directory,
    find_best_match_in_listing,
)


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
    
    ftpserver: str = "ftp://vmf.geo.tuwien.ac.at"
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
    
    vmf1_pattern: str = r"VMFG_{year}{doy}\.H(00|06|12|18)"
    vmf3_pattern: str = r"VMF3_{year}{doy}\.H(00|06|12|18)"
    vmf1_daily: str = r"VMFG_{year}{doy}.*"
    vmf3_daily: str = r"VMF3_{year}{doy}.*"
    
    def vmf1_regex(self, date: datetime.date, hour: Optional[int] = None) -> str:
        """
        Return regex for VMF1 file.
        
        Parameters
        ----------
        date : datetime.date
            Target date.
        hour : int, optional
            Specific hour (0, 6, 12, 18). If None, matches any available hour.
        """
        year, doy = _parse_date(date)
        if hour is not None:
            return f"VMFG_{year}{doy}\\.H{hour:02d}"
        return self.vmf1_daily.format(year=year, doy=doy)
    
    def vmf3_regex(self, date: datetime.date, hour: Optional[int] = None) -> str:
        """
        Return regex for VMF3 file.
        
        Parameters
        ----------
        date : datetime.date
            Target date.
        hour : int, optional
            Specific hour (0, 6, 12, 18). If None, matches any available hour.
        """
        year, doy = _parse_date(date)
        if hour is not None:
            return f"VMF3_{year}{doy}\\.H{hour:02d}"
        return self.vmf3_daily.format(year=year, doy=doy)


class VMFProductSource(BaseModel):
    """
    FTP source for Vienna Mapping Functions (VMF) troposphere products.
    
    VMF products provide:
        - Hydrostatic and wet mapping function coefficients
        - Zenith hydrostatic and wet delay values
        - Used for precise tropospheric modeling in PPP
    
    Example
    -------
    >>> source = VMFProductSource()
    >>> result = source.query_vmf1(datetime.date(2025, 1, 1))
    >>> print(result.url)
    ftp://vmf.geo.tuwien.ac.at/trop_products/GRID/VMF1/VMF1_OP/2025/VMFG_2025001.H00
    """
    
    directory_source: VMFDirectorySource = VMFDirectorySource()
    file_regex: VMFFileRegex = VMFFileRegex()
    
    def _search(
        self,
        directory: str,
        regex: str,
        product_type: str,
    ) -> Optional[AtmosphericFileResult]:
        """Search FTP directory for matching file."""
        try:
            listing = ftp_list_directory(
                self.directory_source.ftpserver, directory, timeout=60
            )
            if not listing:
                return None
                
            filename = find_best_match_in_listing(listing, regex)
            if filename:
                return AtmosphericFileResult(
                    ftpserver=self.directory_source.ftpserver,
                    directory=directory,
                    filename=filename,
                    product_type=product_type,
                    quality=AtmosphericProductQuality.FINAL,
                )
        except Exception:
            pass
        
        return None
    
    def query_vmf1(
        self,
        date: datetime.date,
        hour: Optional[int] = None,
    ) -> Optional[AtmosphericFileResult]:
        """
        Query for VMF1 troposphere product.
        
        Parameters
        ----------
        date : datetime.date
            Date for which to retrieve VMF1 product.
        hour : int, optional
            Specific hour (0, 6, 12, 18). If None, returns first available.
            
        Returns
        -------
        AtmosphericFileResult or None
            File result if found.
        """
        directory = self.directory_source.vmf1_directory(date)
        regex = self.file_regex.vmf1_regex(date, hour)
        return self._search(directory, regex, "vmf1")
    
    def query_vmf3(
        self,
        date: datetime.date,
        hour: Optional[int] = None,
    ) -> Optional[AtmosphericFileResult]:
        """
        Query for VMF3 troposphere product.
        
        Parameters
        ----------
        date : datetime.date
            Date for which to retrieve VMF3 product.
        hour : int, optional
            Specific hour (0, 6, 12, 18). If None, returns first available.
            
        Returns
        -------
        AtmosphericFileResult or None
            File result if found.
        """
        directory = self.directory_source.vmf3_directory(date)
        regex = self.file_regex.vmf3_regex(date, hour)
        return self._search(directory, regex, "vmf3")
    
    def query_all_hours(
        self,
        date: datetime.date,
        product: Literal["vmf1", "vmf3"] = "vmf1",
    ) -> list[AtmosphericFileResult]:
        """
        Query all available hourly files for a given date.
        
        Parameters
        ----------
        date : datetime.date
            Target date.
        product : str
            Either "vmf1" or "vmf3".
            
        Returns
        -------
        list[AtmosphericFileResult]
            List of all matching hourly files.
        """
        results = []
        for hour in [0, 6, 12, 18]:
            if product == "vmf1":
                result = self.query_vmf1(date, hour)
            else:
                result = self.query_vmf3(date, hour)
            
            if result is not None:
                results.append(result)
        
        return results


# ---------------------------------------------------------------------------
# Unified Atmospheric Product Source
# ---------------------------------------------------------------------------

# Import GIM source from ionosphere_resources to avoid duplication
from .ionosphere_resources import CODEGIMProductSource


class AtmosphericProductSource(BaseModel):
    """
    Unified interface for all atmospheric correction products.
    
    Provides a single entry point to query:
        - GIM (ionosphere maps) from CODE (via ionosphere_resources)
        - VMF1/VMF3 (troposphere) from VMF server
    
    Example
    -------
    >>> atm = AtmosphericProductSource()
    >>> gim = atm.query_gim(datetime.date(2025, 1, 1))
    >>> vmf = atm.query_vmf(datetime.date(2025, 1, 1), version="vmf3")
    """
    
    gim_source: CODEGIMProductSource = CODEGIMProductSource()
    vmf_source: VMFProductSource = VMFProductSource()
    
    def query_gim(
        self,
        date: datetime.date,
    ) -> Optional[AtmosphericFileResult]:
        """
        Query for GIM ionosphere product.
        
        Parameters
        ----------
        date : datetime.date
            Target date.
            
        Returns
        -------
        AtmosphericFileResult or None
        """
        result = self.gim_source.query(date)
        if result is not None:
            # Convert IonosphereFileResult to AtmosphericFileResult for backward compatibility
            return AtmosphericFileResult(
                ftpserver=result.ftpserver,
                directory=result.directory,
                filename=result.filename,
                product_type="gim",
                quality=AtmosphericProductQuality.FINAL,
            )
        return None
    
    def query_vmf(
        self,
        date: datetime.date,
        version: Literal["vmf1", "vmf3"] = "vmf1",
        hour: Optional[int] = None,
    ) -> Optional[AtmosphericFileResult]:
        """
        Query for VMF troposphere product.
        
        Parameters
        ----------
        date : datetime.date
            Target date.
        version : str
            VMF version ("vmf1" or "vmf3").
        hour : int, optional  
            Specific epoch hour (0, 6, 12, 18).
            
        Returns
        -------
        AtmosphericFileResult or None
        """
        if version == "vmf1":
            return self.vmf_source.query_vmf1(date, hour)
        return self.vmf_source.query_vmf3(date, hour)
