"""
ANTEX (Antenna Exchange Format) Resources
==========================================

This module provides FTP/HTTP resources for downloading ANTEX files containing
antenna phase center corrections (PCO/PCV) for GNSS processing.

ANTEX File Types
----------------
    - **IGS Standard ANTEX**: Official IGS antenna calibrations
      Format: ``igs{frame}_{week}.atx`` or ``igs{frame}.atx``
      Examples: ``igs20_2345.atx``, ``igs14.atx``
      
    - **CODE MGEX ANTEX**: Extended calibrations for CODE MGEX products
      Files: ``M14.ATX`` (before 2021-05-02), ``M20.ATX`` (after)
      
    - **IGS Repro3 ANTEX**: Calibrations for IGS Reprocessing 3
      Format: ``igsR3*.atx``

Reference Frames
----------------
    - **igs08**: IGS08 reference frame (legacy)
    - **igs14**: IGS14/IGb14 reference frame (2017-2024)
    - **igs20**: IGS20 reference frame (2024+)
    - **igsR3**: IGS Reprocessing 3 frame

Servers
-------
    - IGS (files.igs.org): Primary source for standard ANTEX files
    - CLSIGS (igs.ign.fr): IGS data center mirror
    - CODE (ftp.aiub.unibe.ch): CODE MGEX and Repro3 ANTEX
    - IGS-RF (igs-rf.ign.fr): IGS Reference Frame ANTEX files
"""

import datetime
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Literal, Optional, List

from pydantic import BaseModel

from .utils import (
    ftp_list_directory,
    find_best_match_in_listing,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# MJD 59336 = 2021-05-02, cutoff between M14.ATX and M20.ATX
CODE_MGEX_MJD_CUTOFF = 59336
CODE_MGEX_DATE_CUTOFF = datetime.date(2021, 5, 2)


class AntexFrameType(str, Enum):
    """Reference frame types for ANTEX files."""
    
    IGS08 = "igs08"
    IGS14 = "igs14"
    IGS20 = "igs20"
    IGSR3 = "igsR3"


@dataclass
class AntexFileResult:
    """
    Result of a successful ANTEX file query.

    Attributes
    ----------
    ftpserver : str
        FTP/HTTP host URL.
    directory : str
        Remote directory path.
    filename : str
        Remote filename.
    frame_type : AntexFrameType | None
        Reference frame type if known.
    """

    ftpserver: str
    directory: str
    filename: str
    frame_type: Optional[AntexFrameType] = None

    @property
    def url(self) -> str:
        """Full URL to the remote file."""
        host = self.ftpserver.rstrip("/")
        path = self.directory.strip("/")
        return f"{host}/{path}/{self.filename}"


# ---------------------------------------------------------------------------
# IGS Standard ANTEX (files.igs.org)
# ---------------------------------------------------------------------------

class IGSAntexDirectorySource(BaseModel):
    """Directory paths for IGS ANTEX files."""
    
    httpserver: str = "https://files.igs.org"
    current_dir: str = "pub/station/general"
    archive_dir: str = "pub/station/general/pcv_archive"


class IGSAntexFTPSource(BaseModel):
    """
    IGS ANTEX file source from files.igs.org.
    
    Provides access to standard IGS antenna calibration files in both
    current and archived directories.
    
    Examples
    --------
    >>> source = IGSAntexFTPSource()
    >>> result = source.query("igs20")  # Get latest igs20 ANTEX
    >>> result = source.query_by_filename("igs14_2154.atx")  # Specific file
    """
    
    directory_source: IGSAntexDirectorySource = IGSAntexDirectorySource()
    
    # Regex patterns for different ANTEX filename formats
    _pattern_frame_week: str = r"igs{frame}_\d{{4}}\.atx"
    _pattern_frame_only: str = r"igs{frame}\.atx"

    def _build_search_urls(self, filename: str) -> List[str]:
        """Build list of potential URLs to search for a file."""
        return [
            f"{self.directory_source.httpserver}/{self.directory_source.current_dir}/{filename}",
            f"{self.directory_source.httpserver}/{self.directory_source.archive_dir}/{filename}",
            f"{self.directory_source.httpserver}/{self.directory_source.archive_dir}/{filename}.gz",
        ]

    def get_current_url(self, frame: AntexFrameType = AntexFrameType.IGS20) -> str:
        """
        Get URL for the current/latest ANTEX file for a reference frame.
        
        Parameters
        ----------
        frame : AntexFrameType
            Reference frame (default: IGS20)
            
        Returns
        -------
        str
            URL pattern for finding the latest ANTEX file
        """
        frame_str = frame.value.replace("igs", "")
        return f"{self.directory_source.httpserver}/{self.directory_source.current_dir}/igs{frame_str}.atx"

    def query_by_filename(self, filename: str) -> AntexFileResult:
        """
        Query for a specific ANTEX filename.
        
        Parameters
        ----------
        filename : str
            ANTEX filename (e.g., "igs20_2345.atx", "igs14.atx")
            
        Returns
        -------
        AntexFileResult
            Result with URL components
        """
        # Ensure .atx extension
        if not filename.lower().endswith(".atx"):
            filename = f"{filename}.atx"
            
        # Detect frame type from filename
        frame_type = None
        if "igs20" in filename.lower():
            frame_type = AntexFrameType.IGS20
        elif "igs14" in filename.lower():
            frame_type = AntexFrameType.IGS14
        elif "igs08" in filename.lower():
            frame_type = AntexFrameType.IGS08
        elif "igsr3" in filename.lower():
            frame_type = AntexFrameType.IGSR3

        # Check if it contains week number -> likely archived
        if re.search(r"igs\d{2}_\d{4}", filename):
            directory = self.directory_source.archive_dir
        else:
            directory = self.directory_source.current_dir

        return AntexFileResult(
            ftpserver=self.directory_source.httpserver,
            directory=directory,
            filename=filename,
            frame_type=frame_type,
        )

    def query(
        self,
        frame: AntexFrameType = AntexFrameType.IGS20,
    ) -> AntexFileResult:
        """
        Query for the latest ANTEX file for a reference frame.
        
        Parameters
        ----------
        frame : AntexFrameType
            Reference frame to query
            
        Returns
        -------
        AntexFileResult
            Result pointing to the current ANTEX file
        """
        frame_str = frame.value.replace("igs", "")
        filename = f"igs{frame_str}.atx"
        
        return AntexFileResult(
            ftpserver=self.directory_source.httpserver,
            directory=self.directory_source.current_dir,
            filename=filename,
            frame_type=frame,
        )


# ---------------------------------------------------------------------------
# CODE MGEX ANTEX (ftp.aiub.unibe.ch)
# ---------------------------------------------------------------------------

class CODEMGEXAntexDirectorySource(BaseModel):
    """Directory paths for CODE MGEX ANTEX files."""
    
    ftpserver: str = "ftp://ftp.aiub.unibe.ch"
    antex_dir: str = "CODE_MGEX/CODE"


class CODEMGEXAntexFTPSource(BaseModel):
    """
    CODE MGEX ANTEX file source.
    
    CODE provides extended antenna calibrations for MGEX products:
    - M14.ATX: Used before 2021-05-02 (MJD 59336)
    - M20.ATX: Used from 2021-05-02 onwards
    
    These files extend the standard IGS14 calibrations with additional
    antennas tracked by the MGEX network.
    
    Examples
    --------
    >>> source = CODEMGEXAntexFTPSource()
    >>> result = source.query(datetime.date(2020, 1, 1))  # Returns M14.ATX
    >>> result = source.query(datetime.date(2023, 1, 1))  # Returns M20.ATX
    """
    
    directory_source: CODEMGEXAntexDirectorySource = CODEMGEXAntexDirectorySource()

    def query(self, date: datetime.date) -> AntexFileResult:
        """
        Query for the appropriate CODE MGEX ANTEX file for a date.
        
        Parameters
        ----------
        date : datetime.date
            Processing date to determine M14 vs M20
            
        Returns
        -------
        AntexFileResult
            Result pointing to M14.ATX or M20.ATX
        """
        if date < CODE_MGEX_DATE_CUTOFF:
            filename = "M14.ATX"
        else:
            filename = "M20.ATX"
            
        return AntexFileResult(
            ftpserver=self.directory_source.ftpserver,
            directory=self.directory_source.antex_dir,
            filename=filename,
            frame_type=AntexFrameType.IGS14,  # Both are based on IGS14
        )

    def m14(self) -> str:
        """Full URL to M14.ATX."""
        return f"{self.directory_source.ftpserver}/{self.directory_source.antex_dir}/M14.ATX"
    
    def m20(self) -> str:
        """Full URL to M20.ATX."""
        return f"{self.directory_source.ftpserver}/{self.directory_source.antex_dir}/M20.ATX"


# ---------------------------------------------------------------------------
# IGS Repro3 ANTEX (igs-rf.ign.fr, aiub)
# ---------------------------------------------------------------------------

class IGSR3AntexDirectorySource(BaseModel):
    """Directory paths for IGS Repro3 ANTEX files."""
    
    primary_server: str = "ftp://igs-rf.ign.fr"
    primary_dir: str = "pub/IGSR3"
    
    fallback_server: str = "ftp://ftp.aiub.unibe.ch"
    fallback_dir: str = "users/villiger"


class IGSR3AntexFTPSource(BaseModel):
    """
    IGS Reprocessing 3 ANTEX file source.
    
    IGS Repro3 uses special antenna calibrations available from:
    - Primary: ftp://igs-rf.ign.fr/pub/IGSR3/
    - Fallback: ftp://ftp.aiub.unibe.ch/users/villiger/
    
    Examples
    --------
    >>> source = IGSR3AntexFTPSource()
    >>> result = source.query()  # Returns igsR3.atx location
    """
    
    directory_source: IGSR3AntexDirectorySource = IGSR3AntexDirectorySource()
    default_filename: str = "igsR3.atx"

    def query(self, filename: Optional[str] = None) -> AntexFileResult:
        """
        Query for IGS Repro3 ANTEX file.
        
        Parameters
        ----------
        filename : str, optional
            Specific filename (default: igsR3.atx)
            
        Returns
        -------
        AntexFileResult
            Result pointing to primary server location
        """
        if filename is None:
            filename = self.default_filename
            
        # Ensure .atx extension
        if not filename.lower().endswith(".atx"):
            filename = f"{filename}.atx"
            
        return AntexFileResult(
            ftpserver=self.directory_source.primary_server,
            directory=self.directory_source.primary_dir,
            filename=filename,
            frame_type=AntexFrameType.IGSR3,
        )

    def query_fallback(self, filename: Optional[str] = None) -> AntexFileResult:
        """
        Query fallback server (AIUB) for IGS Repro3 ANTEX file.
        
        Parameters
        ----------
        filename : str, optional
            Specific filename (default: igsR3.atx)
            
        Returns
        -------
        AntexFileResult
            Result pointing to fallback server location
        """
        if filename is None:
            filename = self.default_filename
            
        if not filename.lower().endswith(".atx"):
            filename = f"{filename}.atx"
            
        return AntexFileResult(
            ftpserver=self.directory_source.fallback_server,
            directory=self.directory_source.fallback_dir,
            filename=filename,
            frame_type=AntexFrameType.IGSR3,
        )


# ---------------------------------------------------------------------------
# CLSIGS ANTEX Mirror (igs.ign.fr)
# ---------------------------------------------------------------------------

class CLSIGSAntexDirectorySource(BaseModel):
    """Directory paths for CLSIGS ANTEX files."""
    
    ftpserver: str = "ftp://igs.ign.fr"
    antex_dir: str = "pub/igs/igscb/station/general"


class CLSIGSAntexFTPSource(BaseModel):
    """
    CLSIGS mirror for IGS ANTEX files.
    
    Provides access to standard IGS ANTEX files via the CLSIGS data center.
    Useful as a fallback when files.igs.org is unavailable.
    
    Examples
    --------
    >>> source = CLSIGSAntexFTPSource()
    >>> result = source.query("igs20.atx")
    """
    
    directory_source: CLSIGSAntexDirectorySource = CLSIGSAntexDirectorySource()

    def query(self, filename: str) -> AntexFileResult:
        """
        Query for an ANTEX file by name.
        
        Parameters
        ----------
        filename : str
            ANTEX filename
            
        Returns
        -------
        AntexFileResult
            Result with URL components
        """
        if not filename.lower().endswith(".atx"):
            filename = f"{filename}.atx"
            
        # Detect frame type
        frame_type = None
        lower_name = filename.lower()
        if "igs20" in lower_name:
            frame_type = AntexFrameType.IGS20
        elif "igs14" in lower_name:
            frame_type = AntexFrameType.IGS14
        elif "igs08" in lower_name:
            frame_type = AntexFrameType.IGS08
        elif "igsr3" in lower_name:
            frame_type = AntexFrameType.IGSR3
            
        return AntexFileResult(
            ftpserver=self.directory_source.ftpserver,
            directory=self.directory_source.antex_dir,
            filename=filename,
            frame_type=frame_type,
        )

    def igs20(self) -> str:
        """Full URL to igs20.atx."""
        return f"{self.directory_source.ftpserver}/{self.directory_source.antex_dir}/igs20.atx"

    def igs14(self) -> str:
        """Full URL to igs14.atx."""
        return f"{self.directory_source.ftpserver}/{self.directory_source.antex_dir}/igs14.atx"


# ---------------------------------------------------------------------------
# Unified ANTEX Source
# ---------------------------------------------------------------------------

class AntexProductSource(BaseModel):
    """
    Unified ANTEX product source with fallback support.
    
    Provides a single interface to query ANTEX files from multiple sources
    with automatic fallback handling.
    
    Attributes
    ----------
    igs_source : IGSAntexFTPSource
        Primary IGS ANTEX source (files.igs.org)
    clsigs_source : CLSIGSAntexFTPSource
        CLSIGS mirror for IGS files
    code_mgex_source : CODEMGEXAntexFTPSource
        CODE MGEX extended calibrations
    repro3_source : IGSR3AntexFTPSource
        IGS Reprocessing 3 calibrations
        
    Examples
    --------
    >>> source = AntexProductSource()
    >>> result = source.query_standard("igs20")
    >>> result = source.query_code_mgex(datetime.date(2023, 1, 1))
    >>> result = source.query_repro3()
    """
    
    igs_source: IGSAntexFTPSource = IGSAntexFTPSource()
    clsigs_source: CLSIGSAntexFTPSource = CLSIGSAntexFTPSource()
    code_mgex_source: CODEMGEXAntexFTPSource = CODEMGEXAntexFTPSource()
    repro3_source: IGSR3AntexFTPSource = IGSR3AntexFTPSource()

    def query_standard(
        self, 
        frame: AntexFrameType = AntexFrameType.IGS20
    ) -> AntexFileResult:
        """
        Query for standard IGS ANTEX file.
        
        Parameters
        ----------
        frame : AntexFrameType
            Reference frame (default: IGS20)
            
        Returns
        -------
        AntexFileResult
            Result from IGS source
        """
        return self.igs_source.query(frame)

    def query_by_filename(self, filename: str) -> AntexFileResult:
        """
        Query for a specific ANTEX file by name.
        
        Parameters
        ----------
        filename : str
            ANTEX filename
            
        Returns
        -------
        AntexFileResult
            Result from IGS source
        """
        return self.igs_source.query_by_filename(filename)

    def query_code_mgex(self, date: datetime.date) -> AntexFileResult:
        """
        Query for CODE MGEX ANTEX file appropriate for a date.
        
        Parameters
        ----------
        date : datetime.date
            Processing date
            
        Returns
        -------
        AntexFileResult
            Result pointing to M14.ATX or M20.ATX
        """
        return self.code_mgex_source.query(date)

    def query_repro3(self) -> AntexFileResult:
        """
        Query for IGS Repro3 ANTEX file.
        
        Returns
        -------
        AntexFileResult
            Result from primary Repro3 source
        """
        return self.repro3_source.query()

    def query_repro3_fallback(self) -> AntexFileResult:
        """
        Query fallback server for IGS Repro3 ANTEX file.
        
        Returns
        -------
        AntexFileResult
            Result from fallback AIUB source
        """
        return self.repro3_source.query_fallback()
