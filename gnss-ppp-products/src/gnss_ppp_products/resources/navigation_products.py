import datetime
from typing import Literal, Optional
from pydantic import BaseModel
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


class Group1NavFileRegex(BaseModel):
    product_broadcast_rnx3: str = "BRDC.*{year}{doy}.*rnx.*"
    product_broadcast_rnx2: str = "brdc{doy}0.{yy}{constellation}.gz"

    def broadcast_rnx3(self, date: datetime.datetime, quality: ProductQuality) -> str:
        year, doy = _parse_date(date)
        return self.product_broadcast_rnx3.format(
            quality=quality.value, year=year, doy=doy
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
    rinex_nav: str = "pub/gps/data/daily/{year}/{doy}/{yy}p"


class WuhanNavFileFTPProductSource(FTPProductSource):
    product_filesource_regex: Group1NavFileRegex = Group1NavFileRegex()
    product_directory_source: WuhanNavFileDirectorySourceFTP = WuhanNavFileDirectorySourceFTP()

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
                ftpserver=self.product_directory_source.ftpserver,
                directory=directory,
                filename=filename,
                quality=quality,
            )
        return None

    def query(
        self,
        product: Literal[
            "rinex_3_nav",
            "rinex_2_nav"
        ],
        date: datetime.date,
        quality: Optional[ProductQuality] = None,
        constellation: Optional[ConstellationCode] = None,
    ) -> Optional[FTPFileResult]:
        match product:

            case "rinex_3_nav":
                regex = self.product_filesource_regex.broadcast_rnx3(date, quality)
                directory = self.product_directory_source.rinex_nav_dir(date)
            case "rinex_2_nav":
                assert (
                    constellation is not None
                ), "Constellation code required for rinex_2_nav"
                regex = self.product_filesource_regex.broadcast_rnx2(
                    date, quality, constellation
                )
                directory = self.product_directory_source.rinex_nav_dir(date)
            case _:
                raise ValueError(f"Unknown product type: {product}")

        if regex is None or directory is None:
            raise ValueError(f"Regex or directory not defined for product {product}")

        try:
            ftp_file_result = self._search(regex, directory, quality)
            return ftp_file_result
        except Exception as e:
            print(f"Error querying FTP for product {product}: {e}")
            return None


class CLSIGSNavFileDirectorySourceFTP(BaseModel):
    ftpserver: str = "ftp://igs.ign.fr"
    rinex_nav: str = "pub/igs/data/{year}/{doy}"

class CLSIGSNavFileFTPProductSource(WuhanNavFileFTPProductSource):
    product_directory_source: CLSIGSNavFileDirectorySourceFTP = CLSIGSNavFileDirectorySourceFTP()
