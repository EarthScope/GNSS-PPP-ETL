"""
Reference Tables Resources
==========================

This module provides resources for downloading reference tables used in 
GNSS processing:

    - **Leap seconds**: UTC-TAI offset tables
    - **Satellite parameters**: Satellite metadata and properties

Servers
-------
    - Wuhan (igs.gnsswhu.cn): Primary source for PRIDE-PPPAR tables
    - CDDIS (gdc.cddis.eosdis.nasa.gov): IERS leap second files
"""

from dataclasses import dataclass
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel

from .base import ResourceQueryResult, DownloadProtocol
from .ftp_servers import WUHAN_FTP, CDDIS_FTP


class ReferenceTableType(str, Enum):
    """Types of reference tables available."""
    
    LEAP_SECONDS = "leap_seconds"
    SAT_PARAMETERS = "sat_parameters"


@dataclass
class ReferenceTableResult(ResourceQueryResult):
    """
    Result of a successful reference table query.

    Attributes
    ----------
    server : str
        Server URL (FTP).
    directory : str
        Remote directory path.
    filename : str
        Remote filename.
    protocol : DownloadProtocol
        Protocol for downloading (FTP).
    table_type : ReferenceTableType
        Type of reference table.
    """

    table_type: ReferenceTableType = ReferenceTableType.LEAP_SECONDS


class WuhanProductTableFTPSource(BaseModel):
    """
    FTP source for PRIDE-PPPAR reference tables from Wuhan University.
    
    Available tables:
        - leap_seconds: Leap second table (leap.sec)
        - sat_parameters: Satellite parameters table
    
    Example
    -------
    >>> source = WuhanProductTableFTPSource()
    >>> result = source.query(product="leap_seconds")
    >>> print(result.url)
    """
    
    ftpserver: str = WUHAN_FTP
    _leap_seconds_dir: str = "pub/whu/phasebias/table"
    _leap_seconds_file: str = "leap.sec"
    _sat_parameters_dir: str = "pub/whu/phasebias/table"
    _sat_parameters_file: str = "sat_parameters"

    def query(
        self,
        product: Literal["leap_seconds", "sat_parameters"] = "leap_seconds",
    ) -> ReferenceTableResult:
        """
        Query for a reference table.
        
        Parameters
        ----------
        product : str
            Table type: "leap_seconds" or "sat_parameters".
            
        Returns
        -------
        ReferenceTableResult
            File result with URL information.
        """
        if product == "leap_seconds":
            return ReferenceTableResult(
                server=self.ftpserver,
                directory=self._leap_seconds_dir,
                filename=self._leap_seconds_file,
                protocol=DownloadProtocol.FTP,
                table_type=ReferenceTableType.LEAP_SECONDS,
            )
        elif product == "sat_parameters":
            return ReferenceTableResult(
                server=self.ftpserver,
                directory=self._sat_parameters_dir,
                filename=self._sat_parameters_file,
                protocol=DownloadProtocol.FTP,
                table_type=ReferenceTableType.SAT_PARAMETERS,
            )
        else:
            raise ValueError(f"Unknown product type: {product}")

    # Legacy methods for backward compatibility
    def leap_sec(self) -> str:
        return self.ftpserver + "/" + self._leap_seconds_dir + "/" + self._leap_seconds_file
    
    def sat_parameters(self) -> str:
        return self.ftpserver + "/" + self._sat_parameters_dir + "/" + self._sat_parameters_file
    

class CDDISProductTableFTPSource(BaseModel):
    """
    FTP source for IERS reference tables from CDDIS.
    
    Available tables:
        - leap_seconds: IERS leap second file
    
    Example
    -------
    >>> source = CDDISProductTableFTPSource()
    >>> result = source.query(product="leap_seconds")
    >>> print(result.url)
    """
    
    ftpserver: str = CDDIS_FTP
    _leap_seconds_dir: str = "pub/products/iers"
    _leap_seconds_file: str = "leapsec.dat"

    def query(
        self,
        product: Literal["leap_seconds"] = "leap_seconds",
    ) -> ReferenceTableResult:
        """
        Query for a reference table.
        
        Parameters
        ----------
        product : str
            Table type: "leap_seconds".
            
        Returns
        -------
        ReferenceTableResult
            File result with URL information.
        """
        if product == "leap_seconds":
            return ReferenceTableResult(
                server=self.ftpserver,
                directory=self._leap_seconds_dir,
                filename=self._leap_seconds_file,
                protocol=DownloadProtocol.FTP,
                table_type=ReferenceTableType.LEAP_SECONDS,
            )
        else:
            raise ValueError(f"Unknown product type: {product}")

    # Legacy method for backward compatibility
    def leap_sec(self) -> str:
        return self.ftpserver + "/" + self._leap_seconds_dir + "/" + self._leap_seconds_file
    