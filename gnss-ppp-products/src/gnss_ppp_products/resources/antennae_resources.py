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
import requests
from pydantic import BaseModel

from .utils import (
    ftp_list_directory,
    find_best_match_in_listing,
    _parse_date,
    _date_to_gps_week,
)

logger = logging.getLogger(__name__)


def _extract_filenames_from_html(html: str) -> list[str]:
    """
    Extract filenames from an Apache/nginx HTML directory listing.
    
    Parses <a href="filename"> tags to get file names.
    """
    # Match href attributes that look like filenames (not directories or parent links)
    pattern = r'<a href="([^"?/][^"?]*)"'
    matches = re.findall(pattern, html)
    # Filter out non-file entries and decode URL encoding
    from urllib.parse import unquote
    filenames = []
    for match in matches:
        decoded = unquote(match)
        # Skip parent directory links and query strings
        if decoded and not decoded.startswith('?') and not decoded.endswith('/'):
            filenames.append(decoded)
    return filenames


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

class IGSAntexHTTPSource(BaseModel):
    """HTTP source for IGS ANTEX files."""
    
    httpserver: str = "https://files.igs.org"
    current_dir: str = "pub/station/general"
    archive_dir: str = "pub/station/general/pcv_archive"
    
    def _determine_frame(self, date: datetime.date | datetime.datetime) -> str:
        """Determine the appropriate IGS frame based on date."""
        if isinstance(date, datetime.datetime):
            date = date.date()
        # IGS frame transitions:
        # - igs08: 2011-04-17 to 2017-01-29 (ITRF2008)
        # - igs14: 2017-01-29 to 2024-04-14 (ITRF2014)
        # - igs20: 2024-04-14 onwards (ITRF2020)
        if date >= datetime.date(2024, 4, 14):
            return "20"
        elif date >= datetime.date(2017, 1, 29):
            return "14"
        else:
            return "08"
    
    def _find_antex_file_strict(self,atx_week_pattern: re.Pattern,gps_week: int) -> Optional[str]:

        try:
            logger.info(f"Querying IGS ANTEX at {self.httpserver}/{self.archive_dir}/")
            response = requests.get(f"{self.httpserver}/{self.archive_dir}/", timeout=30)
            response.raise_for_status()
            # Parse HTML to extract filenames
            filenames = _extract_filenames_from_html(response.text)
            matches = [f for f in filenames if re.match(atx_week_pattern, f)]
            gps_week_matches = {f: int(re.search(r"igs\d+_(\d{4})\.atx", f).group(1)) for f in matches}
            # find the file with the largest gps week that is less than or equal to the target gps_week
            best_match = None
            for f, week in gps_week_matches.items():
                if week <= gps_week:
                    if best_match is None or week > gps_week_matches[best_match]:
                        best_match = f
            if best_match:
                full_url = f"{self.httpserver}/{self.archive_dir}/{best_match}"
                return full_url
            return None
            
        except requests.RequestException as e:
            logger.error(f"Failed to retrieve strict ANTEX file from IGS archive: {e}")
            return None
    
    def _find_antex_file_current(self,atx_current_pattern: re.Pattern) -> Optional[str]:
        try:
            logger.info(f"Querying IGS ANTEX at {self.httpserver}/{self.current_dir}/")
            response = requests.get(f"{self.httpserver}/{self.current_dir}/", timeout=30)
            response.raise_for_status()
            # Parse HTML to extract filenames
            filenames = _extract_filenames_from_html(response.text)
            matches = [f for f in filenames if re.match(atx_current_pattern, f)]

            if matches:
                filename = matches[0]
                full_url = f"{self.httpserver}/{self.current_dir}/{filename}"
                return full_url  # Return the first match (should be the latest)
            return None
            
        except requests.RequestException as e:
            logger.error(f"Failed to retrieve current ANTEX file from IGS: {e}")
            return None
        
    def query(self, date: datetime.datetime, strict:bool=True) -> AntexFileResult:
        """
        Query for the appropriate ANTEX file for a given date.
        
        Parameters
        ----------
        date : datetime.datetime
            Processing date
        
        Returns
        -------
        AntexFileResult
            Result pointing to the ANTEX file
        """
        
        gps_week = _date_to_gps_week(date)
        
        # Determine frame version
        frame = self._determine_frame(date)
        
        current_gps_week = _date_to_gps_week(datetime.datetime.today().astimezone(datetime.timezone.utc))
        atx_week_pattern = re.compile(f"igs{frame}_[0-9]{{4}}\\.atx")
        atx_current_pattern = re.compile(f"igs{frame}\\.atx")

        filename: Optional[str] = None
        if gps_week < current_gps_week and strict:
            # use archive directory
            filename: Optional[str] = self._find_antex_file_strict(atx_week_pattern, gps_week)
        if not filename:
            # Fall back to current directory
            filename = self._find_antex_file_current(atx_current_pattern)

        if not filename:
            logger.warning(f"No ANTEX file for igs{frame} found in IGS listing")
            return AntexFileResult(
                ftpserver=self.httpserver,
                directory=self.current_dir,
                filename="",
                frame_type=None,
            )
        # Try week-specific file first, then fall back to current file
        # use a regex to find the max week file for the frame that is less than gps_week

    
        atnx_frame_type = "igs" + frame
        return AntexFileResult(
            ftpserver=self.httpserver,
            directory=self.current_dir,
            filename=filename,
            frame_type=AntexFrameType(atnx_frame_type),
        )

