import datetime
from typing import Literal, Optional
from .base import (
    FTPFileResult,
    FTPProductSource,
    ProductDirectorySourceFTP,
    ProductFileSourceRegex,
    ProductQuality,
    DownloadProtocol,
)
from .utils import (
    _parse_date,
    _date_to_gps_week,
    ftp_list_directory,
    find_best_match_in_listing,
)


class Group1FileRegex(ProductFileSourceRegex):
    product_sp3: str = "{quality}.*{year}{doy}.*SP3.*"
    product_obx: str = "{quality}.*{year}{doy}.*OBX.*"
    product_clk: str = "{quality}.*{year}{doy}.*CLK.*"
    product_sum: str = "{quality}.*{year}{doy}.*SUM.*"
    product_bias: str = "{quality}.*{year}{doy}.*BIA.*"
    product_erp: str = "{quality}.*{year}{doy}.*ERP.*"

    def sp3(self, date: datetime.datetime, quality: ProductQuality) -> str:
        year, doy = _parse_date(date)
        return self.product_sp3.format(quality=quality.value, year=year, doy=doy)

    def obx(self, date: datetime.datetime, quality: ProductQuality) -> str:
        year, doy = _parse_date(date)
        return self.product_obx.format(quality=quality.value, year=year, doy=doy)

    def clk(self, date: datetime.datetime, quality: ProductQuality) -> str:
        year, doy = _parse_date(date)
        return self.product_clk.format(quality=quality.value, year=year, doy=doy)

    def erp(self, date: datetime.datetime, quality: ProductQuality) -> str:
        year, doy = _parse_date(date)
        return self.product_erp.format(quality=quality.value, year=year, doy=doy)

    def sum(self, date: datetime.datetime, quality: ProductQuality) -> str:
        year, doy = _parse_date(date)
        return self.product_sum.format(quality=quality.value, year=year, doy=doy)

    def bias(self, date: datetime.datetime, quality: ProductQuality) -> str:
        year, doy = _parse_date(date)
        return self.product_bias.format(quality=quality.value, year=year, doy=doy)


class WuhanDirectorySourceFTP(ProductDirectorySourceFTP):
    ftpserver: str = "ftp://igs.gnsswhu.cn"
    product_sp3: str = "pub/whu/phasebias/{year}/orbit/"
    product_orbit: str = "pub/whu/phasebias/{year}/orbit/"
    product_clk: str = "pub/whu/phasebias/{year}/clock/"
    product_sum: str = "pub/whu/phasebias/{year}/clock/"
    product_bias: str = "pub/whu/phasebias/{year}/bias/"
    product_erp: str = "pub/whu/phasebias/{year}/orbit/"
    product_obx: str = "pub/whu/phasebias/{year}/orbit/"

    def sp3(self, date: datetime.datetime) -> str:
        year, doy = _parse_date(date)
        return self.product_sp3.format(year=year)

    def orbit(self, date: datetime.datetime) -> str:
        year, doy = _parse_date(date)
        return self.product_orbit.format(year=year)

    def clk(self, date: datetime.datetime) -> str:
        year, doy = _parse_date(date)
        return self.product_clk.format(year=year)

    def sum(self, date: datetime.datetime) -> str:
        year, doy = _parse_date(date)
        return self.product_sum.format(year=year)

    def erp(self, date: datetime.datetime) -> str:
        year, doy = _parse_date(date)
        return self.product_erp.format(year=year)

    def bias(self, date: datetime.datetime) -> str:
        year, doy = _parse_date(date)
        return self.product_bias.format(year=year)

    def obx(self, date: datetime.datetime) -> str:
        year, doy = _parse_date(date)
        return self.product_obx.format(year=year)


class WuhanFTPProductSource(FTPProductSource):
    product_filesource_regex: Group1FileRegex = Group1FileRegex()
    product_directory_source: WuhanDirectorySourceFTP = WuhanDirectorySourceFTP()

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
        product: Literal[
            "sp3",
            "orbit",
            "clk",
            "sum",
            "bias",
            "erp",
            "obx",
        ],
        date: datetime.date,
        quality: Optional[ProductQuality] = None,
    ) -> Optional[FTPFileResult]:
        match product:
            case "sp3" | "orbit":
                regex = self.product_filesource_regex.sp3(date, quality)
                directory = self.product_directory_source.sp3(date)
            case "clk":
                regex = self.product_filesource_regex.clk(date, quality)
                directory = self.product_directory_source.clk(date)
            case "sum":
                regex = self.product_filesource_regex.sum(date, quality)
                directory = self.product_directory_source.sum(date)
            case "bias":
                regex = self.product_filesource_regex.bias(date, quality)
                directory = self.product_directory_source.bias(date)
            case "erp":
                regex = self.product_filesource_regex.erp(date, quality)
                directory = self.product_directory_source.erp(date)
            case "obx":
                regex = self.product_filesource_regex.obx(date, quality)
                directory = self.product_directory_source.obx(date)

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


class CLSIGSDirectorySourceFTP(ProductDirectorySourceFTP):
    ftpserver: str = "ftp://igs.ign.fr"
    product_sp3: str = "pub/igs/products/{gps_week}"
    product_orbit: str = "pub/igs/products/{gps_week}"
    product_clk: str = "pub/igs/products/{gps_week}"
    product_sum: str = "pub/igs/products/{gps_week}"
    product_bias: str = "pub/igs/products/{gps_week}"
    product_erp: str = "pub/igs/products/{gps_week}"
    product_obx: str = "pub/igs/products/{gps_week}"

    def sp3(self, date: datetime.datetime) -> str:
        gps_week = _date_to_gps_week(date)
        return self.product_sp3.format(gps_week=gps_week)

    def orbit(self, date: datetime.datetime) -> str:
        gps_week = _date_to_gps_week(date)
        return self.product_orbit.format(gps_week=gps_week)

    def sum(self, date: datetime.datetime) -> str:
        gps_week = _date_to_gps_week(date)
        return self.product_sum.format(gps_week=gps_week)

    def clk(self, date: datetime.datetime) -> str:
        gps_week = _date_to_gps_week(date)
        return self.product_clk.format(gps_week=gps_week)

    def erp(self, date: datetime.datetime) -> str:
        gps_week = _date_to_gps_week(date)
        return self.product_erp.format(gps_week=gps_week)

    def bias(self, date: datetime.datetime) -> str:
        gps_week = _date_to_gps_week(date)
        return self.product_bias.format(gps_week=gps_week)

    def obx(self, date: datetime.datetime) -> str:
        gps_week = _date_to_gps_week(date)
        return self.product_obx.format(gps_week=gps_week)


class CLSIGSFTPProductSource(WuhanFTPProductSource):
    product_directory_source: CLSIGSDirectorySourceFTP = CLSIGSDirectorySourceFTP()


class KASIDirectorySourceFTP(ProductDirectorySourceFTP):
    """Directory structure for KASI (Korea) FTP server - fallback source."""

    ftpserver: str = "ftp://nfs.kasi.re.kr"
    product_sp3: str = "gps/products/{gps_week}"
    product_orbit: str = "gps/products/{gps_week}"
    product_clk: str = "gps/products/{gps_week}"
    product_sum: str = "gps/products/{gps_week}"
    product_bias: str = "gps/products/{gps_week}"
    product_erp: str = "gps/products/{gps_week}"
    product_obx: str = "gps/products/{gps_week}"

    def sp3(self, date: datetime.datetime) -> str:
        gps_week = _date_to_gps_week(date)
        return self.product_sp3.format(gps_week=gps_week)

    def orbit(self, date: datetime.datetime) -> str:
        gps_week = _date_to_gps_week(date)
        return self.product_orbit.format(gps_week=gps_week)

    def clk(self, date: datetime.datetime) -> str:
        gps_week = _date_to_gps_week(date)
        return self.product_clk.format(gps_week=gps_week)

    def sum(self, date: datetime.datetime) -> str:
        gps_week = _date_to_gps_week(date)
        return self.product_sum.format(gps_week=gps_week)

    def erp(self, date: datetime.datetime) -> str:
        gps_week = _date_to_gps_week(date)
        return self.product_erp.format(gps_week=gps_week)

    def bias(self, date: datetime.datetime) -> str:
        gps_week = _date_to_gps_week(date)
        return self.product_bias.format(gps_week=gps_week)

    def obx(self, date: datetime.datetime) -> str:
        gps_week = _date_to_gps_week(date)
        return self.product_obx.format(gps_week=gps_week)


class KASIFTPProductSource(WuhanFTPProductSource):
    product_directory_source: KASIDirectorySourceFTP = KASIDirectorySourceFTP()


class CDDISDirectorySourceFTP(ProductDirectorySourceFTP):
    """Directory structure for CDDIS (ESA/NASA) FTP server - fallback source."""

    ftpserver: str = "ftp://gssc.esa.int"
    product_sp3: str = "gnss/products/{gps_week}"
    product_orbit: str = "gnss/products/{gps_week}"
    product_clk: str = "gnss/products/{gps_week}"
    product_sum: str = "gnss/products/{gps_week}"
    product_bias: str = "gnss/products/{gps_week}"
    product_erp: str = "gnss/products/{gps_week}"
    product_obx: str = "gnss/products/{gps_week}"

    def sp3(self, date: datetime.datetime) -> str:
        gps_week = _date_to_gps_week(date)
        return self.product_sp3.format(gps_week=gps_week)

    def orbit(self, date: datetime.datetime) -> str:
        gps_week = _date_to_gps_week(date)
        return self.product_orbit.format(gps_week=gps_week)

    def clk(self, date: datetime.datetime) -> str:
        gps_week = _date_to_gps_week(date)
        return self.product_clk.format(gps_week=gps_week)

    def sum(self, date: datetime.datetime) -> str:
        gps_week = _date_to_gps_week(date)
        return self.product_sum.format(gps_week=gps_week)

    def erp(self, date: datetime.datetime) -> str:
        gps_week = _date_to_gps_week(date)
        return self.product_erp.format(gps_week=gps_week)

    def bias(self, date: datetime.datetime) -> str:
        gps_week = _date_to_gps_week(date)
        return self.product_bias.format(gps_week=gps_week)

    def obx(self, date: datetime.datetime) -> str:
        gps_week = _date_to_gps_week(date)
        return self.product_obx.format(gps_week=gps_week)


class CDDISFTPProductSource(WuhanFTPProductSource):
    product_directory_source: CDDISDirectorySourceFTP = CDDISDirectorySourceFTP()


class IGNMGEXDirectorySourceFTP(ProductDirectorySourceFTP):
    """
    Directory structure for IGN MGEX FTP server.
    
    Multi-GNSS products from ftp://igs.ign.fr/pub/igs/products/mgex/
    
    Used by PRIDE-PPPAR for rapid products (WUM0MGXRAP).
    """

    ftpserver: str = "ftp://igs.ign.fr"
    product_sp3: str = "pub/igs/products/mgex/{gps_week}"
    product_orbit: str = "pub/igs/products/mgex/{gps_week}"
    product_clk: str = "pub/igs/products/mgex/{gps_week}"
    product_sum: str = "pub/igs/products/mgex/{gps_week}"
    product_bias: str = "pub/igs/products/mgex/{gps_week}"
    product_erp: str = "pub/igs/products/mgex/{gps_week}"
    product_obx: str = "pub/igs/products/mgex/{gps_week}"

    def sp3(self, date: datetime.datetime) -> str:
        gps_week = _date_to_gps_week(date)
        return self.product_sp3.format(gps_week=gps_week)

    def orbit(self, date: datetime.datetime) -> str:
        gps_week = _date_to_gps_week(date)
        return self.product_orbit.format(gps_week=gps_week)

    def clk(self, date: datetime.datetime) -> str:
        gps_week = _date_to_gps_week(date)
        return self.product_clk.format(gps_week=gps_week)

    def sum(self, date: datetime.datetime) -> str:
        gps_week = _date_to_gps_week(date)
        return self.product_sum.format(gps_week=gps_week)

    def erp(self, date: datetime.datetime) -> str:
        gps_week = _date_to_gps_week(date)
        return self.product_erp.format(gps_week=gps_week)

    def bias(self, date: datetime.datetime) -> str:
        gps_week = _date_to_gps_week(date)
        return self.product_bias.format(gps_week=gps_week)

    def obx(self, date: datetime.datetime) -> str:
        gps_week = _date_to_gps_week(date)
        return self.product_obx.format(gps_week=gps_week)


class IGNMGEXFTPProductSource(WuhanFTPProductSource):
    """
    MGEX product source from IGN (igs.ign.fr).
    
    Provides multi-GNSS orbit, clock, attitude, ERP, and bias products.
    Primary source for WUM0MGXRAP (Wuhan University rapid MGEX products).
    """
    product_directory_source: IGNMGEXDirectorySourceFTP = IGNMGEXDirectorySourceFTP()
