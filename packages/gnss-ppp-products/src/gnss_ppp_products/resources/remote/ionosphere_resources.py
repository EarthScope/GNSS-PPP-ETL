"""
Ionosphere Products FTP/HTTP Resources
======================================

This module provides resources for downloading ionosphere correction products
used in GNSS Precise Point Positioning (PPP):

    - **GIM** (Global Ionosphere Maps): VTEC grids in IONEX format for ionospheric delay correction
    - **Higher-order ionospheric corrections**: Second-order ionospheric delay modeling

Product Categories
------------------
GIM products provide global Vertical Total Electron Content (VTEC) maps which are
essential for single-frequency PPP and beneficial for higher-order ionospheric
corrections in dual-frequency PPP.

Quality Tiers
-------------
    - FINAL: Post-processed combined solution (highest accuracy, ~2 week latency)
    - RAPID: Near real-time solution (~1 day latency)
    - PREDICTED: Forecast solution (for real-time applications)

Servers
-------
    - CODE (ftp.aiub.unibe.ch): Primary source for CODE GIM products
    - CDDIS (gdc.cddis.eosdis.nasa.gov): NASA archive mirror
    - IGS (igs.ign.fr): IGS combined products

File Formats
------------
    - IONEX: IONosphere map EXchange format (standard IGS format)
    - Legacy naming (pre-2022): CODG{doy}0.{yy}I.Z
    - Long-form naming (2022+): COD0OPSFIN_{year}{doy}0000_01D_01H_GIM.INX.gz
"""

import datetime
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel

from .base import FTPFileResult, ProductQuality, ResourceQueryResult, DownloadProtocol
from .ftp_servers import AIUB_FTP, WUHAN_FTP, CDDIS_FTP
from .utils import (
    ftp_list_directory,
    find_best_match_in_listing,
    _parse_date,
    datetime_to_mjd
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums and Data Classes
# ---------------------------------------------------------------------------


class IonosphereProductQuality(str, Enum):
    """Quality levels for ionosphere products."""

    FINAL = "final"
    RAPID = "rapid"
    PREDICTED = "predicted"


class IonosphereProductType(str, Enum):
    """Types of ionosphere products available."""

    GIM = "gim"  # Global Ionosphere Maps (VTEC grids)


class IonosphereAnalysisCenter(str, Enum):
    """Analysis centers that produce ionosphere products."""
    JPL = "jpl"  # Jet Propulsion Laboratory
    IGS = "igs"  # International GNSS Service
    ESA = "esa"  # European Space Agency
    UPC = "upc"  # Universitat Politècnica de Catalunya
    COD = "cod"  # Center for Orbit Determination in Europe
    EMR = "emr"  # Natural Resources Canada


# Alias for backward compatibility
IonosphereProductSource = IonosphereAnalysisCenter


@dataclass
class IonosphereFileResult(ResourceQueryResult):
    """
    Result of a successful ionosphere product query.

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
    product_type : IonosphereProductType
        Product type (GIM).
    quality : IonosphereProductQuality
        Quality level at which the file was found.
    """

    product_type: IonosphereProductType = IonosphereProductType.GIM
    quality: IonosphereProductQuality = IonosphereProductQuality.FINAL


# ---------------------------------------------------------------------------
# CODE GIM Products (Primary Source - AIUB Bern)
# ---------------------------------------------------------------------------


class CODEGIMDirectorySource(BaseModel):
    """
    Directory structure for CODE GIM products at AIUB Bern.

    Products available:
        - CODG: Final CODE GIM (combined global ionosphere map)
        - CORG: Rapid CODE GIM
        - COD: Predicted CODE GIM

    Directory structure:
        ftp://ftp.aiub.unibe.ch/CODE/{year}/
    """

    ftpserver: str = AIUB_FTP
    base_path: str = "CODE/{year}"

    def directory(self, date: datetime.date) -> str:
        """Return the GIM directory for a given date."""
        year, _ = _parse_date(date)
        return self.base_path.format(year=year)


class CODEGIMFileRegex(BaseModel):
    """
    Regex patterns for CODE GIM products.

 
    """

    # New long-form patterns (2022+)
    ion_pattern_new: str = "COD0OPSFIN_{year}{doy}0000_01D_01H_GIM.INX.gz"
    ion_pattern_legacy: str = "CODG{doy}0.{yy}I.Z"
    
    def ion(self, date: datetime.datetime) -> str:
        """Return regex for CODE GIM product based on date."""
        year, doy = _parse_date(date)
        yy = year[2:]
        major_julian_day = datetime_to_mjd(date)
        if major_julian_day > 59909:  # January 1, 2022 in MJD
            return self.ion_pattern_new.format(year=year, doy=doy)
        else:
            return self.ion_pattern_legacy.format(doy=doy, yy=yy)


class CODEGIMProductSource(BaseModel):
    """
    FTP source for CODE Global Ionosphere Maps (GIM).

    GIM products provide global VTEC (Vertical Total Electron Content) maps
    in IONEX format, used for ionospheric delay corrections in PPP processing.

    Example
    -------
    >>> source = CODEGIMProductSource()
    >>> result = source.query(datetime.date(2025, 1, 1))
    >>> print(result.url)
    ftp://ftp.aiub.unibe.ch/CODE/2025/COD0OPSFIN_20250010000_01D_01H_GIM.INX.gz

    >>> # Query older data with legacy naming
    >>> result = source.query(datetime.date(2020, 6, 15))
    >>> print(result.url)
    ftp://ftp.aiub.unibe.ch/CODE/2020/CODG1670.20I.Z
    """

    directory_source: CODEGIMDirectorySource = CODEGIMDirectorySource()
    file_regex: CODEGIMFileRegex = CODEGIMFileRegex()

    def query(
        self,
        date: datetime.date,
        center: IonosphereProductSource = IonosphereProductSource.COD, #paceholder
        quality: IonosphereProductQuality = IonosphereProductQuality.FINAL, #placeholder
    ) -> Optional[IonosphereFileResult]:
        """
        Query for a CODE GIM product file.

        Parameters
        ----------
        date : datetime.date
            Date for which to retrieve the GIM product.
        center : IonosphereProductSource
            Analysis center providing the GIM product.
        quality : IonosphereProductQuality
            Quality level (FINAL, RAPID, or PREDICTED).

        Returns
        -------
        IonosphereFileResult or None
            File result if found, otherwise None.
        """
        directory = self.directory_source.directory(date)
        regex = self.file_regex.ion(date)

        try:
            listing = ftp_list_directory(
                self.directory_source.ftpserver, directory, timeout=60
            )
            if not listing:
                logger.debug(f"No listing for {self.directory_source.ftpserver}/{directory}")
                return None

            filename = find_best_match_in_listing(listing, regex)
            if filename:
                return IonosphereFileResult(
                    server=self.directory_source.ftpserver,
                    directory=directory,
                    filename=filename,
                    protocol=DownloadProtocol.FTP,
                    product_type=IonosphereProductType.GIM,
                )
        except Exception as e:
            logger.debug(f"Error querying CODE GIM: {e}")

        return None


# ---------------------------------------------------------------------------
# Wuhan University GIM Products (Asia-Pacific Mirror)
# ---------------------------------------------------------------------------


class WuhanGIMFileRegex(BaseModel):
    """
    Regex patterns for GIM products at Wuhan University IGS Data Center.

    Wuhan University hosts multiple analysis center products:
        - igsg: IGS combined GIM
        - codg: CODE final GIM
        - jplg: JPL GIM
        - esag: ESA GIM
        - upcg: UPC GIM

    example full urls:
    ftp://igs.gnsswhu.cn/pub/gps/products/ionex/2023/361/JPL0OPSRAP_20233610000_01D_02H_GIM.INX.gz
    ftp://igs.gnsswhu.cn/pub/gps/products/ionex/2023/361/ESA0OPSRAP_20233610000_01D_02H_GIM.INX.gz
    """

    regex: str = "{center}0OPS{quality}_{year}{doy}0000_01D_.*\\.INX\\.gz"
    # TODO: Add input for hourly (ex: 02H vs 01H)
    def ion(self, date: datetime.date, center: IonosphereAnalysisCenter, quality: IonosphereProductQuality) -> str:
        """Return regex for GIM product at Wuhan."""
        year, doy = _parse_date(date)
        return self.regex.format(center=center.value.upper(), quality=quality.value.upper()[:3], year=year, doy=doy)


class WuhanGIMDirectorySource(BaseModel):
    """
    Directory structure for GIM Ionosphere products at Wuhan University IGS Data Center.

    Mirrors CODE and IGS GIM products.

    Directory structure:
        ftp://igs.gnsswhu.cn/pub/gps/products/ionex/{year}/{doy}/
    """

    ftpserver: str = WUHAN_FTP
    base_path: str = "pub/gps/products/ionex/{year}/{doy}"

    def directory(self, date: datetime.date) -> str:
        """Return the GIM directory for a given date."""
        year, doy = _parse_date(date)
        return self.base_path.format(year=year, doy=doy)


class WuhanGIMProductSource(BaseModel):
    """
    FTP source for GIM products at Wuhan University.

    Provides access to IGS and CODE GIM products mirrored from primary sources.
    Good alternative for users in Asia-Pacific region.

    Example
    -------
    >>> source = WuhanGIMProductSource()
    >>> result = source.query(datetime.date(2025, 1, 1))
    >>> print(result.url)
    ftp://igs.gnsswhu.cn/pub/gps/products/ionex/2025/001/codg0010.25i.Z
    """

    directory_source: WuhanGIMDirectorySource = WuhanGIMDirectorySource()
    file_regex: WuhanGIMFileRegex = WuhanGIMFileRegex()

    def query(
        self,
        date: datetime.date,
        center: IonosphereProductSource = IonosphereProductSource.COD,
        quality: IonosphereProductQuality = IonosphereProductQuality.FINAL,
    ) -> Optional[IonosphereFileResult]:
        """
        Query for a GIM product file at Wuhan.

        Parameters
        ----------
        date : datetime.date
            Date for which to retrieve the GIM product.
        center : IonosphereProductSource
            Analysis center: IonosphereProductSource.IGS (combined), IonosphereProductSource.COD (CODE), or IonosphereProductSource.JPL (JPL).
        quality : IonosphereProductQuality
            Quality of the GIM product: IonosphereProductQuality.FINAL (final), IonosphereProductQuality.RAP (rapid), etc.

        Returns
        -------
        IonosphereFileResult or None
            File result if found, otherwise None.
        """
        directory = self.directory_source.directory(date)

        regex = self.file_regex.ion(date, center, quality)

        try:
            listing = ftp_list_directory(
                self.directory_source.ftpserver, directory, timeout=60
            )
            if not listing:
                logger.debug(f"No listing for {self.directory_source.ftpserver}/{directory}")
                return None

            filename = find_best_match_in_listing(listing, regex)
            if filename:
                return IonosphereFileResult(
                    server=self.directory_source.ftpserver,
                    directory=directory,
                    filename=filename,
                    protocol=DownloadProtocol.FTP,
                    product_type=IonosphereProductType.GIM,
                    quality=quality,
                )
        except Exception as e:
            logger.debug(f"Error querying Wuhan GIM: {e}")

        return None

# ---------------------------------------------------------------------------
# CDDIS GIM Products (NASA Mirror)
# ---------------------------------------------------------------------------


class CDDISGIMDirectorySource(BaseModel):
    """
    Directory structure for GIM products at NASA CDDIS.

    CDDIS mirrors IGS combined GIM products and CODE products.

    Note: CDDIS requires FTPS (TLS) for anonymous sessions.

    Directory structure:
        ftp://gdc.cddis.eosdis.nasa.gov/gnss/products/ionex/{year}/{doy}/
    """

    ftpserver: str = CDDIS_FTP
    base_path: str = "gnss/products/ionex/{year}/{doy}"

    def directory(self, date: datetime.date) -> str:
        """Return the GIM directory for a given date."""
        year, doy = _parse_date(date)
        return self.base_path.format(year=year, doy=doy)


class CDDISGIMProductSource(BaseModel):
    """
    FTP source for GIM products at NASA CDDIS.

    Provides access to IGS combined and individual analysis center GIM products.
    Useful as a fallback when primary CODE server is unavailable.

    Note: CDDIS requires FTPS (TLS) for anonymous sessions.

    Example
    -------
    >>> source = CDDISGIMProductSource()
    >>> result = source.query(datetime.date(2025, 1, 1), center="igs")
    >>> print(result.url)
    ftp://gdc.cddis.eosdis.nasa.gov/gnss/products/ionex/2025/001/igsg0010.25i.Z
    """

    directory_source: CDDISGIMDirectorySource = CDDISGIMDirectorySource()
    file_regex: WuhanGIMFileRegex = WuhanGIMFileRegex()  # Reuse regex patterns from Wuhan since CDDIS uses same naming

    def query(
        self,
        date: datetime.date,
        center: IonosphereProductSource = IonosphereProductSource.COD,
        quality: IonosphereProductQuality = IonosphereProductQuality.FINAL,
    ) -> Optional[IonosphereFileResult]:
        """
        Query for a GIM product file at CDDIS.

        Parameters
        ----------
        date : datetime.date
            Date for which to retrieve the GIM product.
        center : IonosphereProductSource
            Analysis center: IonosphereProductSource.COD (combined), IonosphereProductSource.COD (CODE), or IonosphereProductSource.JPL (JPL).
        quality : IonosphereProductQuality
            Quality of the GIM product.

        Returns
        -------
        IonosphereFileResult or None
            File result if found, otherwise None.
        """
        directory = self.directory_source.directory(date)

        if center not in [
            IonosphereProductSource.IGS,
            IonosphereProductSource.ESA,
            IonosphereProductSource.COD,
            IonosphereProductSource.EMR,
        ]:
            raise ValueError("CDDIS GIM query only supports IGS, ESA, COD, and EMR centers")
        regex = self.file_regex.ion(date, center, quality)

        try:
            listing = ftp_list_directory(
                self.directory_source.ftpserver, directory, timeout=60, use_tls=True
            )
            if not listing:
                logger.debug(
                    f"No listing for {self.directory_source.ftpserver}/{directory}"
                )
                return None

            filename = find_best_match_in_listing(listing, regex)
            if filename:
                return IonosphereFileResult(
                    server=self.directory_source.ftpserver,
                    directory=directory,
                    filename=filename,
                    protocol=DownloadProtocol.FTPS,
                    product_type=IonosphereProductType.GIM,
                    quality=quality,
                )
        except Exception as e:
            logger.debug(f"Error querying CDDIS GIM: {e}")

        return None
