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
from typing import Literal, Optional, List, Tuple
import requests
from pydantic import BaseModel

from .utils import (
    ftp_list_directory,
    find_best_match_in_listing,
    _parse_date,
    _date_to_gps_week,
)

logger = logging.getLogger(__name__)


class IGSAntexReferenceFrameType(str, Enum):
    """Reference frame types for ANTEX files."""
    IGS05 = "igs05"
    IGS08 = "igs08"
    IGS14 = "igs14"
    IGS20 = "igs20"
    IGSR3 = "igsR3"


def determine_frame(
    date: datetime.date | datetime.datetime,
) -> IGSAntexReferenceFrameType:
    """Determine the appropriate IGS frame based on date."""
    if isinstance(date, datetime.datetime):
        date = date.date()

    if date >= datetime.date(2022, 11, 27):
        return IGSAntexReferenceFrameType.IGS20
    elif date >= datetime.date(2017, 1, 29):
        return IGSAntexReferenceFrameType.IGS14
    elif date >= datetime.date(2011,4,17):
        return IGSAntexReferenceFrameType.IGS08
    elif date >= datetime.date(2006, 11, 5):
        return IGSAntexReferenceFrameType.IGS05  # Assuming a placeholder for the earliest frame
    else:
        raise ValueError(f"No suitable IGS frame found for date {date}")

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
        if decoded and not decoded.startswith("?") and not decoded.endswith("/"):
            filenames.append(decoded)
    return filenames


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# MJD 59336 = 2021-05-02, cutoff between M14.ATX and M20.ATX
CODE_MGEX_MJD_CUTOFF = 59336
CODE_MGEX_DATE_CUTOFF = datetime.date(2021, 5, 2)


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
    full_url: Optional[str] = None
    frame_type: Optional[IGSAntexReferenceFrameType] = None


# ---------------------------------------------------------------------------
# IGS Standard ANTEX (files.igs.org)
# ---------------------------------------------------------------------------


class IGSAntexHTTPSource(BaseModel):
    """HTTP source for IGS ANTEX files."""

    httpserver: str = "https://files.igs.org"
    current_dir: str = "pub/station/general"
    archive_dir: str = "pub/station/general/pcv_archive"

    def _find_antex_file_strict(
        self, atx_week_pattern: re.Pattern, gps_week: int
    ) -> Optional[Tuple[str, str, str]]:

        try:
            logger.info(f"Querying IGS ANTEX at {self.httpserver}/{self.archive_dir}/")
            response = requests.get(
                f"{self.httpserver}/{self.archive_dir}/", timeout=30
            )
            response.raise_for_status()
            # Parse HTML to extract filenames
            filenames = _extract_filenames_from_html(response.text)
            matches = [f for f in filenames if re.match(atx_week_pattern, f)]
            gps_week_matches = {
                f: int(re.search(r"igs\d+_(\d{4})\.atx", f).group(1)) for f in matches
            }
            # find the file with the largest gps week that is less than or equal to the target gps_week
            best_match = None
            for f, week in gps_week_matches.items():
                if week <= gps_week:
                    if best_match is None or week > gps_week_matches[best_match]:
                        best_match = f
            if best_match:
                return self.httpserver, self.archive_dir, best_match
            return None

        except requests.RequestException as e:
            logger.error(f"Failed to retrieve strict ANTEX file from IGS archive: {e}")
            return None

    def _find_antex_file_current(
        self, atx_current_pattern: re.Pattern
    ) -> Optional[Tuple[str, str, str]]:
        try:
            logger.info(f"Querying IGS ANTEX at {self.httpserver}/{self.current_dir}/")
            response = requests.get(
                f"{self.httpserver}/{self.current_dir}/", timeout=30
            )
            response.raise_for_status()
            # Parse HTML to extract filenames
            filenames = _extract_filenames_from_html(response.text)
            matches = [f for f in filenames if re.match(atx_current_pattern, f)]

            if matches:
                filename = matches[0]
                return (
                    self.httpserver,
                    self.current_dir,
                    filename,
                )  # Return the first match (should be the latest)
            return None

        except requests.RequestException as e:
            logger.error(f"Failed to retrieve current ANTEX file from IGS: {e}")
            return None

    def query(
        self, date: datetime.datetime, strict: bool = True
    ) -> Optional[AntexFileResult]:
        """
        Query for the appropriate ANTEX file for a given date.

        Parameters
        ----------
        date : datetime.datetime
            Processing date
        strict : bool
            If True, attempt to find the week-specific ANTEX file in the archive first (e.g., igs20_2345.atx).
            If False, or if no week-specific file is found, fall back to the current file.

        Returns
        -------
        Optional[AntexFileResult]
            Result pointing to the ANTEX file, or None if no file is found.

        Examples
        --------
        >>> source = IGSAntexHTTPSource()
        >>> date = datetime.datetime(2025, 1, 1)
        >>> result = source.query(date, strict=True)
        >>> print(result.full_url)
        'https://files.igs.org/pub/station/general/pcv_archive/igs20_2343.atx'
        >>> result = source.query(date, strict=False)
        >>> print(result.full_url)
        'https://files.igs.org/pub/station/general/igs20.atx'
        """
        assert isinstance(
            date, (datetime.date, datetime.datetime)
        ), "date must be a datetime.date or datetime.datetime object"

        gps_week = _date_to_gps_week(date)

        # Determine frame version
        frame:IGSAntexReferenceFrameType = determine_frame(date)

        current_gps_week = _date_to_gps_week(
            datetime.datetime.today().astimezone(datetime.timezone.utc)
        )
        atx_week_pattern: re.Pattern = re.compile(f"igs{frame.value[-2:]}_[0-9]{{4}}\\.atx")
        atx_current_pattern: re.Pattern = re.compile(f"igs{frame.value[-2:]}\\.atx")

        result: Optional[Tuple[str, str, str]] = None
        if gps_week < current_gps_week and strict:
            # use archive directory
            result: Optional[Tuple[str, str, str]] = self._find_antex_file_strict(
                atx_week_pattern, gps_week
            )
        if not result:
            # Fall back to current directory
            result = self._find_antex_file_current(atx_current_pattern)

        if not result:
            logger.warning(f"No ANTEX file for igs{frame} found in IGS listing")
            return None
        # Try week-specific file first, then fall back to current file
        # use a regex to find the max week file for the frame that is less than gps_week

        full_url = f"{self.httpserver}/{result[1]}/{result[2]}"
        
        return AntexFileResult(
            ftpserver=self.httpserver,
            directory=result[1],
            filename=result[2],
            full_url=full_url,
            frame_type=frame,
        )


class NGSNOAAAntexHTTPSource(BaseModel):
    """NGS/NOAA ANTEX source (same structure as IGS, but different server)."""

    httpserver: str = "https://www.ngs.noaa.gov/"
    archive_dir: str = "ANTCAL/LoadFile?file="

    def query(self, date: datetime.datetime) -> Optional[AntexFileResult]:
        """Query for the appropriate ANTEX file for a given date."""
        # NGS/NOAA does not have strict week-based files, so we will just return the current file
        frame: IGSAntexReferenceFrameType = determine_frame(date)
        filename = f"ngs{frame.value[-2:]}.atx"
        full_url = f"{self.httpserver}/{self.archive_dir}{filename}"
        # Check if the file exists by making a HEAD request
        try:
            response = requests.head(full_url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Failed to retrieve ANTEX file from NGS/NOAA: {e}")
            return None
        return AntexFileResult(
            ftpserver=self.httpserver,
            directory=self.archive_dir,
            filename=filename,
            full_url=full_url,
            frame_type=frame,
        )


class AstroInstMGEXAntexFTPSource(BaseModel):
    """FTP source for CODE MGEX ANTEX files.
    CODE MGEX products use slightly different antenna calibrations than the standard IGS models. Using mismatched antenna files would introduce systematic errors in the position estimates, so this override ensures consistency between the clock products and the antenna phase center corrections.
    """

    ftpserver: str = "ftp.aiub.unibe.ch"
    directory: str = "/CODE_MGEX/CODE"

    def query(self, date: datetime.datetime) -> Optional[AntexFileResult]:
        """Query for the appropriate CODE MGEX ANTEX file for a given date."""
        if date.date() < CODE_MGEX_DATE_CUTOFF:
            regex = "M14.ATX"
        else:
            regex = "M20.ATX"
        dir_listing = ftp_list_directory(self.ftpserver, self.directory, timeout=60)
        if not dir_listing:
            logger.warning(f"No files found in directory {self.directory} on {self.ftpserver}")
            return None
        filename = find_best_match_in_listing(dir_listing, regex)
        if filename:
            return AntexFileResult(
                ftpserver=self.ftpserver,
                directory=self.directory,
                filename=filename,
                full_url=f"ftp://{self.ftpserver}/{self.directory}/{filename}",
                frame_type=determine_frame(date),
            )
