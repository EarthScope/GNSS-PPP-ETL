"""
LEO Satellite Products Resources
================================

This module provides FTP resources for downloading Low Earth Orbit (LEO) satellite
data products, primarily for GRACE and GRACE-FO missions.

Product Categories
------------------
    - **GRACE/GRACE-FO Level-1B**: Instrument data for LEO satellite PPP
    - **GraceRead Software**: Official software for reading GRACE data

Servers
-------
    - GFZ Potsdam (isdcftp.gfz-potsdam.de): Primary source for GRACE/GRACE-FO data

Usage
-----
These products are used for:
    - LEO satellite precise orbit determination (POD)
    - Low Earth Orbit PPP with GRACE/GRACE-FO satellites
    - Gravity field mission data processing
"""

import datetime
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel

from .base import ResourceQueryResult, DownloadProtocol
from .ftp_servers import GFZ_FTP
from .utils import ftp_list_directory, find_best_match_in_listing

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums and Data Classes
# ---------------------------------------------------------------------------


class GRACEMission(str, Enum):
    """GRACE mission identifiers."""
    
    GRACE = "grace"       # Original GRACE mission (2002-2017)
    GRACE_FO = "grace-fo"  # GRACE Follow-On mission (2018+)


class GRACEInstrument(str, Enum):
    """GRACE instrument types."""
    
    ACC = "ACC"  # Accelerometer
    AHK = "AHK"  # Attitude and Housekeeping
    GNV = "GNV"  # GPS Navigation
    KBR = "KBR"  # K-Band Ranging
    LRI = "LRI"  # Laser Ranging Interferometer (GRACE-FO only)
    SCA = "SCA"  # Star Camera Assembly
    THR = "THR"  # Thruster
    CLK = "CLK"  # Clock
    GPS = "GPS"  # GPS data
    MAS = "MAS"  # Mass change
    TIM = "TIM"  # Time


@dataclass
class GRACEFileResult(ResourceQueryResult):
    """
    Result of a successful GRACE product query.

    Attributes
    ----------
    server : str
        FTP server URL.
    directory : str
        Remote directory path.
    filename : str
        Remote filename.
    protocol : DownloadProtocol
        Protocol for downloading (FTP).
    mission : GRACEMission
        GRACE or GRACE-FO.
    instrument : str
        Instrument type.
    """

    mission: GRACEMission = GRACEMission.GRACE_FO
    instrument: str = ""


# ---------------------------------------------------------------------------
# GFZ GRACE/GRACE-FO Products
# ---------------------------------------------------------------------------


class GFZGRACEDirectorySource(BaseModel):
    """
    Directory structure for GRACE/GRACE-FO products at GFZ Potsdam.
    
    Directory structure:
        ftp://isdcftp.gfz-potsdam.de/grace/Level-1B/JPL/INSTRUMENT/RL02/{year}/
        ftp://isdcftp.gfz-potsdam.de/grace-fo/Level-1B/JPL/INSTRUMENT/RL04/{year}/
    """
    
    ftpserver: str = GFZ_FTP
    
    # GRACE (original mission) paths
    grace_level1b_path: str = "grace/Level-1B/JPL/{instrument}/RL02/{year}"
    
    # GRACE-FO paths
    grace_fo_level1b_path: str = "grace-fo/Level-1B/JPL/{instrument}/RL04/{year}"
    
    # Software path
    software_path: str = "grace/SOFTWARE"
    
    def level1b_directory(
        self, 
        date: datetime.date, 
        mission: GRACEMission,
        instrument: str = "GNV1B"
    ) -> str:
        """Return Level-1B directory for a given date and mission."""
        year = date.year
        if mission == GRACEMission.GRACE_FO:
            return self.grace_fo_level1b_path.format(instrument=instrument, year=year)
        else:
            return self.grace_level1b_path.format(instrument=instrument, year=year)
    
    def software_directory(self) -> str:
        """Return software directory."""
        return self.software_path


class GFZGRACEFileRegex(BaseModel):
    """
    Regex patterns for GRACE/GRACE-FO Level-1B products.
    
    File naming convention:
        {instrument}_{YYYY}-{MM}-{DD}_{satellite}_{release}.{ext}
        
    Examples:
        GNV1B_2024-01-15_C_04.dat.gz
        ACC1B_2024-01-15_D_04.dat.gz
    """
    
    # Combined file pattern (both GRACE-A/B or GRACE-C/D)
    level1b_pattern: str = r"{instrument}_{year}-{month:02d}-{day:02d}_[CD]_\d+\..*"
    
    def level1b(
        self, 
        date: datetime.date, 
        instrument: str = "GNV1B"
    ) -> str:
        """Return regex for Level-1B file."""
        return self.level1b_pattern.format(
            instrument=instrument,
            year=date.year,
            month=date.month,
            day=date.day
        )


class GFZGRACEFTPProductSource(BaseModel):
    """
    FTP source for GRACE/GRACE-FO products from GFZ Potsdam.
    
    Provides Level-1B instrument data and software downloads.
    
    Example
    -------
    >>> source = GFZGRACEFTPProductSource()
    >>> result = source.query(
    ...     date=datetime.date(2024, 1, 15),
    ...     mission=GRACEMission.GRACE_FO,
    ...     product="GNV1B"
    ... )
    >>> print(result.url)
    """
    
    directory_source: GFZGRACEDirectorySource = GFZGRACEDirectorySource()
    file_regex: GFZGRACEFileRegex = GFZGRACEFileRegex()
    
    def query(
        self,
        date: datetime.date,
        product: str = "GNV1B",
        mission: GRACEMission = GRACEMission.GRACE_FO,
    ) -> Optional[GRACEFileResult]:
        """
        Query for a GRACE/GRACE-FO Level-1B product.
        
        Parameters
        ----------
        date : datetime.date
            Date for which to retrieve the product.
        product : str
            Instrument/product type (e.g., "GNV1B", "ACC1B", "SCA1B", "SOFTWARE").
        mission : GRACEMission
            GRACE or GRACE-FO mission.
            
        Returns
        -------
        GRACEFileResult or None
            File result if found.
        """
        if product == "SOFTWARE":
            return self.query_software()
        return self.query_level1b(date=date, mission=mission, instrument=product)
    
    def query_level1b(
        self,
        date: datetime.date,
        mission: GRACEMission = GRACEMission.GRACE_FO,
        instrument: str = "GNV1B",
    ) -> Optional[GRACEFileResult]:
        """
        Query for a GRACE/GRACE-FO Level-1B product.
        
        Parameters
        ----------
        date : datetime.date
            Date for which to retrieve the product.
        mission : GRACEMission
            GRACE or GRACE-FO mission.
        instrument : str
            Instrument type (e.g., "GNV1B", "ACC1B", "SCA1B").
            
        Returns
        -------
        GRACEFileResult or None
            File result if found.
        """
        # Validate mission dates
        if mission == GRACEMission.GRACE and date.year > 2017:
            logger.warning("GRACE mission ended in 2017, use GRACE-FO for later dates")
            return None
        if mission == GRACEMission.GRACE_FO and date.year < 2018:
            logger.warning("GRACE-FO mission started in 2018")
            return None
        
        directory = self.directory_source.level1b_directory(date, mission, instrument)
        regex = self.file_regex.level1b(date, instrument)
        
        try:
            dir_listing = ftp_list_directory(
                self.directory_source.ftpserver, 
                directory, 
                timeout=60
            )
            if not dir_listing:
                logger.debug(f"No directory listing for {directory}")
                return None
            
            filename = find_best_match_in_listing(dir_listing, regex)
            if filename:
                return GRACEFileResult(
                    server=self.directory_source.ftpserver,
                    directory=directory,
                    filename=filename,
                    protocol=DownloadProtocol.FTP,
                    mission=mission,
                    instrument=instrument,
                )
        except Exception as e:
            logger.error(f"Failed to query GRACE product: {e}")
        
        return None
    
    def query_software(
        self,
        software_name: str = "GraceReadSW_L1_2010-03-31.tar.gz"
    ) -> Optional[GRACEFileResult]:
        """
        Query for GRACE read software.
        
        Parameters
        ----------
        software_name : str
            Name of the software package to download.
            
        Returns
        -------
        GRACEFileResult or None
            File result if found.
        """
        directory = self.directory_source.software_directory()
        
        try:
            dir_listing = ftp_list_directory(
                self.directory_source.ftpserver, 
                directory, 
                timeout=60
            )
            if not dir_listing:
                return None
            
            # Find the software file
            if software_name in dir_listing:
                return GRACEFileResult(
                    server=self.directory_source.ftpserver,
                    directory=directory,
                    filename=software_name,
                    protocol=DownloadProtocol.FTP,
                    mission=GRACEMission.GRACE,
                    instrument="SOFTWARE",
                )
            
            # Try to find any matching GraceRead software
            for fname in dir_listing:
                if "GraceReadSW" in fname or "graceread" in fname.lower():
                    return GRACEFileResult(
                        server=self.directory_source.ftpserver,
                        directory=directory,
                        filename=fname,
                        protocol=DownloadProtocol.FTP,
                        mission=GRACEMission.GRACE,
                        instrument="SOFTWARE",
                    )
        except Exception as e:
            logger.error(f"Failed to query GRACE software: {e}")
        
        return None
