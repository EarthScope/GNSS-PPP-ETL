import datetime
from typing import Any, Literal, Optional
from pydantic import BaseModel
import logging

from .base import (
    FTPFileResult,
    FTPProductSource,
    ProductQuality,
    ConstellationCode,
)
from .utils import (
    _parse_date,
    _date_to_gps_week,
    ftp_list_directory,
    find_best_match_in_listing,
)

logger = logging.getLogger(__name__)

class Group1NavFileRegex(BaseModel):
    product_broadcast_rnx3: str = "BRDC.*{year}{doy}.*rnx.*"
    product_broadcast_rnx2: str = "brdc{doy}0.{yy}{constellation}.*"

    def broadcast_rnx3(self, date: datetime.datetime) -> str:
        year, doy = _parse_date(date)
        return self.product_broadcast_rnx3.format(
            year=year, doy=doy
        )

    def broadcast_rnx2(
        self,
        date: datetime.datetime,
        constellation: ConstellationCode,
    ) -> str:
        year, doy = _parse_date(date)
        return self.product_broadcast_rnx2.format(
            doy=doy, yy=year[2:], constellation=constellation.value
        )


class WuhanNavFileDirectorySourceFTP(BaseModel):
    ftpserver: str = "ftp://igs.gnsswhu.cn"
    rinex_nav: str = "pub/gps/data/daily/{year}/{doy}/{yy}{prefix}"

    def rinex_nav_dir(self, date: datetime.date, constellation: ConstellationCode=None) -> str:
        """Return the RINEX navigation directory for a given date."""
        year, doy = _parse_date(date)
        yy = str(year)[-2:]
        if date >= datetime.date(2013,1,1):
            # use multi-gnss merged products after 2013 when they became available, otherwise use constellation-specific directories for older data
            prefix = "p" if constellation is None else constellation.value
        else:
            assert constellation is not None, "Constellation code required for rinex_nav_dir before 2013"
            prefix = constellation.value
        return self.rinex_nav.format(year=year, doy=doy, yy=yy, prefix=prefix)


class WuhanNavFileFTPProductSource(BaseModel):
    product_filesource_regex: Group1NavFileRegex = Group1NavFileRegex()
    product_directory_source: WuhanNavFileDirectorySourceFTP = WuhanNavFileDirectorySourceFTP()

    def _search(
        self, regex: str, directory: str
    ) -> Optional[FTPFileResult]:
        logger.info(f"Searching FTP {self.product_directory_source.ftpserver} in directory {directory} for regex {regex}")
        dir_listing = ftp_list_directory(
            self.product_directory_source.ftpserver, directory, timeout=60
        )
        if not dir_listing:
            logger.info(f"No files found in directory {directory} on {self.product_directory_source.ftpserver}")
            return None
        filename = find_best_match_in_listing(dir_listing, regex)
        if filename:
            return FTPFileResult(
                ftpserver=self.product_directory_source.ftpserver,
                directory=directory,
                filename=filename,
                quality=ProductQuality.FINAL,
            )
        return None

    def query(
        self,
        product: Literal[
            "rinex_3_nav",
            "rinex_2_nav"
        ],
        date: datetime.date,
        constellation: Optional[ConstellationCode] = None,
    ) -> Optional[FTPFileResult]:
        match product:

            case "rinex_3_nav":
                regex = self.product_filesource_regex.broadcast_rnx3(date)
                directory = self.product_directory_source.rinex_nav_dir(date)
            case "rinex_2_nav":
                assert (
                    constellation is not None
                ), "Constellation code required for rinex_2_nav"
                regex = self.product_filesource_regex.broadcast_rnx2(
                    date, constellation
                )
                directory = self.product_directory_source.rinex_nav_dir(date, constellation)
            case _:
                raise ValueError(f"Unknown product type: {product}")

        if regex is None or directory is None:
            raise ValueError(f"Regex or directory not defined for product {product}")

        try:
            ftp_file_result = self._search(regex, directory)
            return ftp_file_result
        except Exception as e:
            logger.error(f"Error querying FTP for product {product}: {e}")
            return None


class CLSIGSNavFileDirectorySourceFTP(BaseModel):
    ftpserver: str = "ftp://igs.ign.fr"
    rinex_nav: str = "pub/igs/data/{year}/{doy}"

    def rinex_nav_dir(self, date: datetime.date,_=None) -> str:
        """Return the RINEX navigation directory for a given date."""
        year, doy = _parse_date(date)
        return self.rinex_nav.format(year=year, doy=doy)

class CLSIGSNavFileFTPProductSource(WuhanNavFileFTPProductSource):
    product_directory_source: CLSIGSNavFileDirectorySourceFTP = CLSIGSNavFileDirectorySourceFTP()

class CDDISNavFileDirectorySourceFTP(BaseModel):
    ftpserver: str = "ftp://gdc.cddis.eosdis.nasa.gov"
    rinex_nav: str = "pub/gps/data/daily/{year}/{doy}/{yy}{prefix}"

    def rinex_nav_dir(self, date: datetime.date, constellation: Optional[ConstellationCode] = None) -> str:
        """Return the RINEX navigation directory for a given date."""
        year, doy = _parse_date(date)
        yy = str(year)[-2:]
        if date >= datetime.date(2013,1,1):
            prefix = "p" if constellation is None else constellation.value
            # use multi-gnss merged products after 2013 when they became available, otherwise use constellation-specific directories for older data
        else:
            assert constellation is not None, "Constellation code required for rinex_nav_dir before 2013"
            prefix = constellation.value

        return self.rinex_nav.format(year=year, doy=doy, yy=yy, prefix=prefix)

class CDDISNavFileFTPProductSource(WuhanNavFileFTPProductSource):
    """CDDIS requires FTPS (TLS) for anonymous sessions."""
    product_directory_source: CDDISNavFileDirectorySourceFTP = CDDISNavFileDirectorySourceFTP()

    def _search(
        self, regex: str, directory: str
    ) -> Optional[FTPFileResult]:
        logger.info(f"Searching FTP {self.product_directory_source.ftpserver} in directory {directory} for regex {regex}")
        # CDDIS requires TLS for anonymous sessions
        dir_listing = ftp_list_directory(
            self.product_directory_source.ftpserver, directory, timeout=60, use_tls=True
        )
        if not dir_listing:
            logger.info(f"No files found in directory {directory} on {self.product_directory_source.ftpserver}")
            return None
        filename = find_best_match_in_listing(dir_listing, regex)
        if filename:
            return FTPFileResult(
                ftpserver=self.product_directory_source.ftpserver,
                directory=directory,
                filename=filename,
                quality=ProductQuality.FINAL,
            )
        return None