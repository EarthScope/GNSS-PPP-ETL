from abc import ABC, abstractmethod
import datetime
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Literal, Optional
import re
from pydantic import BaseModel

class ProductQuality(str, Enum):
    """Enum for product quality levels."""

    FINAL = "FIN"
    RAPID = "RAP"
    REAL_TIME_STREAMING = "RTS"


class ConstellationCode(str, Enum):
    GPS = "n"
    GLONASS = "g"


@dataclass
class FTPFileResult:
    """
    The result of a successful FTP file query.

    Attributes
    ----------
    ftpserver:
        FTP host URL, e.g. ``ftp://igs.gnsswhu.cn``.
    directory:
        Remote directory path (without leading slash), e.g.
        ``pub/whu/phasebias/2025/orbit``.
    filename:
        Remote filename, e.g.
        ``WMC0DEMFIN_20253050000_01D_05M_ORB.SP3.gz``.
    quality:
        The quality level at which the file was found.
    server_name:
        Human-readable server key, e.g. ``"wuhan"``.
    """

    ftpserver: str
    directory: str
    filename: str
    quality: ProductQuality

    @property
    def url(self) -> str:
        """Full FTP URL to the remote file."""
        host = self.ftpserver.rstrip("/")
        path = self.directory.strip("/")
        return f"{host}/{path}/{self.filename}"

    @property
    def quality_label(self) -> str:
        """Short quality label used in filenames (``FIN``, ``RAP``, ``RTS``)."""
        return self.quality.value
    


class ProductFileSourceRegex(BaseModel, ABC):
    """
    Base class for product file sources that are identified by a regex pattern.
    """

    product_sp3: str
    product_obx: str
    product_clk: str
    product_erp: str
    product_sum: str
    product_bias: str
    product_broadcast_rnx3: str
    product_broadcast_rnx2: str

    @abstractmethod
    def sp3(self,date: datetime.datetime) -> str:
        pass
    
    @abstractmethod
    def obx(self,date: datetime.datetime) -> str:
        pass

    @abstractmethod
    def clk(self,date: datetime.datetime) -> str:
        pass

    @abstractmethod
    def erp(self,date: datetime.datetime) -> str:
        pass

    @abstractmethod
    def sum(self,date: datetime.datetime) -> str:
        pass

    @abstractmethod
    def bias(self,date: datetime.datetime) -> str:
        pass

    @abstractmethod
    def broadcast_rnx3(self,date: datetime.datetime) -> str:
        pass

    @abstractmethod
    def broadcast_rnx2(self,date: datetime.datetime) -> str:
        pass


class ProductDirectorySourceFTP(ABC,BaseModel):
    ftpserver: str
    rinex_nav: Optional[str] = None
    product_sp3: Optional[str] = None
    product_clk: Optional[str] = None
    product_sum: Optional[str] = None
    product_bias: Optional[str] = None
    product_erp: Optional[str] = None
    product_obx: Optional[str] = None

    @abstractmethod
    def sp3(self,date: datetime.datetime) -> str:
        pass

    @abstractmethod
    def clk(self,date: datetime.datetime) -> str:
        pass

    @abstractmethod
    def erp(self,date: datetime.datetime) -> str:
        pass

    @abstractmethod
    def obx(self,date: datetime.datetime) -> str:
        pass

    @abstractmethod
    def bias(self,date: datetime.datetime) -> str:
        pass

    @abstractmethod
    def broadcast_rnx(self,date: datetime.datetime) -> str:
        pass

    @abstractmethod
    def sum(self,date: datetime.datetime) -> str:
        pass

class FTPProductSource(ABC,BaseModel):
    """
    Base class for FTP product sources.
    """
    product_filesource_regex: ProductFileSourceRegex
    product_directory_source: ProductDirectorySourceFTP

    @abstractmethod
    def _search(self,regex:str,directory:str,quality: ProductQuality) -> Optional[str]:
        """
        Search the FTP directory for a file matching the given regex and quality.
        Parameters
        ----------
        regex : str
            The regex pattern to match the file name.
        directory : str
            The directory on the FTP server to search.
        quality : ProductQuality
            The quality level of the product file to search for.
        Returns
        -------
        Optional[str]
            The path to the product file if found, otherwise None.
        """
        pass

    @abstractmethod
    def query(
        self,
        date: datetime.datetime,
        product: Literal[
            "rinex_3_nav",
            "rinex_2_nav",
            "sp3",
            "orbit",
            "clk",
            "sum",
            "bias",
            "erp",
            "obx",
        ],
        quality: ProductQuality,
        constellation: ConstellationCode,
    ) -> Optional[str]:
        """
        Query the FTP source for a product file matching the given criteria.
        Parameters
        ----------
        date : datetime.datetime
            The date for which to query the product file.
        quality : ProductQuality
            The quality level of the product file.
        constellation : ConstellationCode
            The GNSS constellation code.
        Returns
        -------
        Optional[str]
            The path to the product file if found, otherwise None.
        """
        pass
