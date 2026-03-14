"""
FTP remote resource schemas for GNSS product retrieval.

Defines ``RemoteQuery`` patterns and ``RemoteResourceFTP`` data classes
for Wuhan IGS, GSSC, CLS/IGN, and Potsdam GFZ servers.
"""

import datetime
import re
from dataclasses import dataclass
from typing import List, Literal, Optional, Tuple

GNSS_START_TIME = datetime.datetime(1980, 1, 6, tzinfo=datetime.timezone.utc)


def _parse_date(date: datetime.date | datetime.datetime) -> Tuple[str, str]:
    """Return ``(year, doy)`` as zero-padded strings."""
    if isinstance(date, datetime.datetime):
        date = date.date()
    year = str(date.year)
    doy = f"{date.timetuple().tm_yday:03d}"
    return year, doy


def _date_to_gps_week(date: datetime.date | datetime.datetime) -> int:
    """Convert a date to a GPS week number."""
    if isinstance(date, datetime.datetime):
        date = date.date()
    time_since_epoch = date - GNSS_START_TIME.date()
    return time_since_epoch.days // 7


# ---------------------------------------------------------------------------
# RemoteQuery
# ---------------------------------------------------------------------------


class RemoteQuery:
    """
    Compiled regex pattern + sort order for matching remote filenames.
    """

    def __init__(self, pattern: re.Pattern, sort_order: List[str] = []):
        self.pattern = pattern
        self.sort_order = sort_order

    @classmethod
    def sp3(cls, date: datetime.date) -> "RemoteQuery":
        year, doy = _parse_date(date)
        pattern = re.compile(rf".*{year}{doy}.*SP3.*")
        return cls(pattern, ["FIN", "RAP", "RTS"])

    @classmethod
    def obx(cls, date: datetime.date) -> "RemoteQuery":
        year, doy = _parse_date(date)
        pattern = re.compile(rf".*{year}{doy}.*OBX.*")
        return cls(pattern, ["FIN", "RAP", "RTS"])

    @classmethod
    def clk(cls, date: datetime.date) -> "RemoteQuery":
        year, doy = _parse_date(date)
        pattern = re.compile(rf".*{year}{doy}.*CLK.*")
        return cls(pattern, ["FIN", "RAP", "RTS"])

    @classmethod
    def sum(cls, date: datetime.date) -> "RemoteQuery":
        year, doy = _parse_date(date)
        pattern = re.compile(rf".*{year}{doy}.*SUM.*")
        return cls(pattern, ["FIN", "RAP", "RTS"])

    @classmethod
    def bias(cls, date: datetime.date) -> "RemoteQuery":
        year, doy = _parse_date(date)
        pattern = re.compile(rf".*{year}{doy}.*BIA.*")
        return cls(pattern, ["FIN", "RAP", "RTS"])

    @classmethod
    def erp(cls, date: datetime.date) -> "RemoteQuery":
        year, doy = _parse_date(date)
        pattern = re.compile(rf".*{year}{doy}.*ERP.*")
        return cls(pattern, ["FIN", "RAP", "RTS"])

    @classmethod
    def rnx3(cls, date: datetime.date) -> "RemoteQuery":
        year, doy = _parse_date(date)
        pattern = re.compile(rf"BRDC.*{year}{doy}.*rnx.*")
        return cls(pattern)

    @classmethod
    def rnx2(
        cls, date: datetime.date, constellation: Literal["gps", "glonass"]
    ) -> "RemoteQuery":
        year, doy = _parse_date(date)
        constellation_tag = {"gps": "n", "glonass": "g"}
        const_tag = constellation_tag[constellation]
        pattern = re.compile(rf"brdc{doy}0.{year[2:]}{const_tag}.gz")
        return cls(pattern)


# ---------------------------------------------------------------------------
# RemoteResourceFTP
# ---------------------------------------------------------------------------


@dataclass
class RemoteResourceFTP:
    """An FTP remote resource (server + directory + query)."""

    ftpserver: str
    directory: str
    remote_query: RemoteQuery
    file_name: Optional[str] = None

    def __str__(self):
        return str(
            {"ftpserver": self.ftpserver, "directory": self.directory, "file": self.file_name}
        )


# ---------------------------------------------------------------------------
# Server definitions
# ---------------------------------------------------------------------------


class WuhanIGS:
    """Wuhan University IGS mirror (igs.gnsswhu.cn)."""

    ftpserver = "ftp://igs.gnsswhu.cn"
    daily_gps_dir = "pub/gps/data/daily"
    daily_product_dir = "pub/whu/phasebias"

    @classmethod
    def get_rinex_2_nav(
        cls, date: datetime.date, constellation: Literal["gps", "glonass"] = "gps"
    ) -> RemoteResourceFTP:
        year, doy = _parse_date(date)
        dir_extension = f"{year}/{doy}/{year[2:]}p"
        directory = "/".join([cls.daily_gps_dir, dir_extension])
        remote_query = RemoteQuery.rnx2(date, constellation)
        return RemoteResourceFTP(ftpserver=cls.ftpserver, directory=directory, remote_query=remote_query)

    @classmethod
    def get_rinex_3_nav(cls, date: datetime.date) -> RemoteResourceFTP:
        remote_query = RemoteQuery.rnx3(date)
        year, doy = _parse_date(date)
        dir_extension = f"{year}/{doy}/{year[2:]}p"
        directory = "/".join([cls.daily_gps_dir, dir_extension])
        return RemoteResourceFTP(ftpserver=cls.ftpserver, directory=directory, remote_query=remote_query)

    @classmethod
    def get_product_sp3(cls, date: datetime.date) -> RemoteResourceFTP:
        year, doy = _parse_date(date)
        directory = "/".join([cls.daily_product_dir, f"{year}/orbit"])
        return RemoteResourceFTP(ftpserver=cls.ftpserver, directory=directory, remote_query=RemoteQuery.sp3(date))

    @classmethod
    def get_product_obx(cls, date: datetime.date) -> RemoteResourceFTP:
        year, doy = _parse_date(date)
        directory = "/".join([cls.daily_product_dir, f"{year}/orbit"])
        return RemoteResourceFTP(ftpserver=cls.ftpserver, directory=directory, remote_query=RemoteQuery.obx(date))

    @classmethod
    def get_product_clk(cls, date: datetime.date) -> RemoteResourceFTP:
        year, doy = _parse_date(date)
        directory = "/".join([cls.daily_product_dir, f"{year}/clock"])
        return RemoteResourceFTP(ftpserver=cls.ftpserver, directory=directory, remote_query=RemoteQuery.clk(date))

    @classmethod
    def get_product_sum(cls, date: datetime.date) -> RemoteResourceFTP:
        year, doy = _parse_date(date)
        directory = "/".join([cls.daily_product_dir, f"{year}/clock"])
        return RemoteResourceFTP(ftpserver=cls.ftpserver, directory=directory, remote_query=RemoteQuery.sum(date))

    @classmethod
    def get_product_bias(cls, date: datetime.date) -> RemoteResourceFTP:
        year, doy = _parse_date(date)
        directory = "/".join([cls.daily_product_dir, f"{year}/bias"])
        return RemoteResourceFTP(ftpserver=cls.ftpserver, directory=directory, remote_query=RemoteQuery.bias(date))

    @classmethod
    def get_product_erp(cls, date: datetime.date) -> RemoteResourceFTP:
        year, doy = _parse_date(date)
        directory = "/".join([cls.daily_product_dir, f"{year}/orbit"])
        return RemoteResourceFTP(ftpserver=cls.ftpserver, directory=directory, remote_query=RemoteQuery.erp(date))


class GSSC:
    """GNSS Science Support center — ESA (gssc.esa.int)."""

    ftpserver = "ftp://gssc.esa.int"
    daily_gps_dir = "gnss/data/daily"

    @classmethod
    def get_rinex_2_nav(
        cls, date: datetime.date, constellation: Literal["gps", "glonass"] = "gps"
    ) -> RemoteResourceFTP:
        year, doy = _parse_date(date)
        directory = "/".join([cls.daily_gps_dir, f"{year}/{doy}"])
        remote_query = RemoteQuery.rnx2(date, constellation)
        return RemoteResourceFTP(ftpserver=cls.ftpserver, directory=directory, remote_query=remote_query)

    @classmethod
    def get_rinex_3_nav(cls, date: datetime.date) -> RemoteResourceFTP:
        remote_query = RemoteQuery.rnx3(date)
        year, doy = _parse_date(date)
        directory = "/".join([cls.daily_gps_dir, f"{year}/{doy}"])
        return RemoteResourceFTP(ftpserver=cls.ftpserver, directory=directory, remote_query=remote_query)


class CLSIGS:
    """CLS IGS data center (igs.ign.fr)."""

    ftpserver = "ftp://igs.ign.fr"
    daily_gps_dir = "pub/igs/data"
    daily_products_dir = "pub/igs/products/mgex"

    constellation_tag = {"gps": "n", "glonass": "g"}

    @classmethod
    def get_rinex_2_nav(
        cls, date: datetime.date, constellation: Literal["gps", "glonass"] = "gps"
    ) -> RemoteResourceFTP:
        year, doy = _parse_date(date)
        directory = "/".join([cls.daily_gps_dir, f"{year}/{doy}"])
        remote_query = RemoteQuery.rnx2(date, constellation)
        return RemoteResourceFTP(ftpserver=cls.ftpserver, directory=directory, remote_query=remote_query)

    @classmethod
    def get_rinex_3_nav(cls, date: datetime.date) -> RemoteResourceFTP:
        remote_query = RemoteQuery.rnx3(date)
        year, doy = _parse_date(date)
        directory = "/".join([cls.daily_gps_dir, f"{year}/{doy}"])
        return RemoteResourceFTP(ftpserver=cls.ftpserver, directory=directory, remote_query=remote_query)

    @classmethod
    def get_product_sp3(cls, date: datetime.date) -> RemoteResourceFTP:
        gps_week = _date_to_gps_week(date)
        directory = "/".join([cls.daily_products_dir, str(gps_week)])
        return RemoteResourceFTP(ftpserver=cls.ftpserver, directory=directory, remote_query=RemoteQuery.sp3(date))

    @classmethod
    def get_product_clk(cls, date: datetime.date) -> RemoteResourceFTP:
        gps_week = _date_to_gps_week(date)
        directory = "/".join([cls.daily_products_dir, str(gps_week)])
        return RemoteResourceFTP(ftpserver=cls.ftpserver, directory=directory, remote_query=RemoteQuery.clk(date))

    @classmethod
    def get_product_erp(cls, date: datetime.date) -> RemoteResourceFTP:
        gps_week = _date_to_gps_week(date)
        directory = "/".join([cls.daily_products_dir, str(gps_week)])
        return RemoteResourceFTP(ftpserver=cls.ftpserver, directory=directory, remote_query=RemoteQuery.erp(date))

    @classmethod
    def get_product_obx(cls, date: datetime.date) -> RemoteResourceFTP:
        gps_week = _date_to_gps_week(date)
        directory = "/".join([cls.daily_products_dir, str(gps_week)])
        return RemoteResourceFTP(ftpserver=cls.ftpserver, directory=directory, remote_query=RemoteQuery.obx(date))

    @classmethod
    def get_product_bias(cls, date: datetime.date) -> RemoteResourceFTP:
        gps_week = _date_to_gps_week(date)
        directory = "/".join([cls.daily_products_dir, str(gps_week)])
        return RemoteResourceFTP(ftpserver=cls.ftpserver, directory=directory, remote_query=RemoteQuery.bias(date))


class Potsdam:
    """GFZ Potsdam (isdcftp.gfz-potsdam.de)."""

    ftpserver = "ftp://isdcftp.gfz-potsdam.de"
    daily_products_dir = "gnss/products/final"
