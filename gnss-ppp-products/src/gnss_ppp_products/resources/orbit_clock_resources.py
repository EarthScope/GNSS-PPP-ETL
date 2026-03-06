import datetime
import logging
from typing import Literal, Optional
from enum import Enum
from pydantic import BaseModel

from .base import (
    FTPFileResult,
    FTPProductSource,
    ProductDirectorySourceFTP,
    ProductFileSourceRegex,
    ProductQuality,
    DownloadProtocol,
)

from .ftp_servers import WUHAN_FTP, IGS_FTP, KASI_FTP, ESA_FTP

from .utils import (
    _parse_date,
    _date_to_gps_week,
    ftp_list_directory,
    find_best_match_in_listing,
)

logger = logging.getLogger(__name__)

class ProductTypes(Enum):
    SP3 = "sp3"
    ORBIT = "orbit"
    CLK = "clk"
    SUM = "sum"
    BIAS = "bias"
    ERP = "erp"
    OBX = "obx" 

# ---------------------------------------------------------------------------
# Regex
# ---------------------------------------------------------------------------


class Group1FileRegex(BaseModel):

    templates: dict[str, str] = {
        "sp3": "{quality}.*{year}{doy}.*SP3.*",
        "orbit": "{quality}.*{year}{doy}.*SP3.*",
        "clk": "{quality}.*{year}{doy}.*CLK.*",
        "sum": "{quality}.*{year}{doy}.*SUM.*",
        "bias": "{quality}.*{year}{doy}.*BIA.*",
        "erp": "{quality}.*{year}{doy}.*ERP.*",
        "obx": "{quality}.*{year}{doy}.*OBX.*",
    }

    def build(self, product: ProductTypes, date: datetime.datetime, quality: ProductQuality) -> str:
        year, doy = _parse_date(date)
        template = self.templates[product.value]
        return template.format(quality=quality.value, year=year, doy=doy)


# ---------------------------------------------------------------------------
# Directory Sources
# ---------------------------------------------------------------------------


class YearDirectorySource(BaseModel):

    ftpserver: str
    base_path: str

    def directory(self, date: datetime.datetime) -> str:
        year, _ = _parse_date(date)
        return self.base_path.format(year=year)


class GPSWeekDirectorySource(BaseModel):

    ftpserver: str
    base_path: str

    def directory(self, date: datetime.datetime) -> str:
        gps_week = _date_to_gps_week(date)
        return self.base_path.format(gps_week=gps_week)


# ---------------------------------------------------------------------------
# Specific Directory Implementations
# ---------------------------------------------------------------------------


class WuhanDirectorySourceFTP(BaseModel):

    ftpserver: str = WUHAN_FTP

    paths: dict[str, str] = {
        "sp3": "pub/whu/phasebias/{year}/orbit/",
        "orbit": "pub/whu/phasebias/{year}/orbit/",
        "clk": "pub/whu/phasebias/{year}/clock/",
        "sum": "pub/whu/phasebias/{year}/clock/",
        "bias": "pub/whu/phasebias/{year}/bias/",
        "erp": "pub/whu/phasebias/{year}/orbit/",
        "obx": "pub/whu/phasebias/{year}/orbit/",
    }

    def directory(self, product: ProductTypes, date: datetime.datetime) -> str:
        year, _ = _parse_date(date)
        return self.paths[product.value].format(year=year)


class CLSIGSDirectorySourceFTP(BaseModel):

    ftpserver: str = IGS_FTP
    base_path: str = "pub/igs/products/{gps_week}"

    def directory(self, product: ProductTypes, date: datetime.datetime) -> str:
        gps_week = _date_to_gps_week(date)
        return self.base_path.format(gps_week=gps_week)


class KASIDirectorySourceFTP(BaseModel):

    ftpserver: str = KASI_FTP
    base_path: str = "gps/products/{gps_week}"

    def directory(self, product: ProductTypes, date: datetime.datetime) -> str:
        gps_week = _date_to_gps_week(date)
        return self.base_path.format(gps_week=gps_week)


class CDDISDirectorySourceFTP(BaseModel):

    ftpserver: str = ESA_FTP
    base_path: str = "gnss/products/{gps_week}"

    def directory(self, product: ProductTypes, date: datetime.datetime) -> str:
        gps_week = _date_to_gps_week(date)
        return self.base_path.format(gps_week=gps_week)


# ---------------------------------------------------------------------------
# Product Source
# ---------------------------------------------------------------------------


class GenericFTPProductSource(FTPProductSource):

    product_filesource_regex: Group1FileRegex
    product_directory_source: ProductDirectorySourceFTP

    def _search(
        self, regex: str, directory: str, quality: ProductQuality
    ) -> Optional[FTPFileResult]:

        dir_listing = ftp_list_directory(
            self.product_directory_source.ftpserver, directory, timeout=60
        )

        if not dir_listing:
            return None

        filename = find_best_match_in_listing(dir_listing, regex)

        if filename:
            return FTPFileResult(
                server=self.product_directory_source.ftpserver,
                directory=directory,
                filename=filename,
                protocol=DownloadProtocol.FTP,
                quality=quality,
            )

        return None

    def query(
        self,
        product: ProductTypes,
        date: datetime.date,
        quality: Optional[ProductQuality] = None,
    ) -> Optional[FTPFileResult]:

        try:

            regex = self.product_filesource_regex.build(product, date, quality)

            directory = self.product_directory_source.directory(product, date)

            return self._search(regex, directory, quality)

        except Exception as e:
            logger.error(f"Error querying FTP for {product}: {e}")
            return None


# ---------------------------------------------------------------------------
# Concrete Sources
# ---------------------------------------------------------------------------


class WuhanFTPProductSource(GenericFTPProductSource):

    product_filesource_regex: Group1FileRegex = Group1FileRegex()
    product_directory_source: WuhanDirectorySourceFTP = WuhanDirectorySourceFTP()


class CLSIGSFTPProductSource(GenericFTPProductSource):

    product_filesource_regex: Group1FileRegex = Group1FileRegex()
    product_directory_source: CLSIGSDirectorySourceFTP = CLSIGSDirectorySourceFTP()


class KASIFTPProductSource(GenericFTPProductSource):

    product_filesource_regex: Group1FileRegex = Group1FileRegex()
    product_directory_source: KASIDirectorySourceFTP = KASIDirectorySourceFTP()


class CDDISFTPProductSource(GenericFTPProductSource):

    product_filesource_regex: Group1FileRegex = Group1FileRegex()
    product_directory_source: CDDISDirectorySourceFTP = CDDISDirectorySourceFTP()