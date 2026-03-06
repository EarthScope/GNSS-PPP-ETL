from abc import ABC, abstractmethod
import datetime
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Literal, Optional
import re
from pydantic import BaseModel


class DownloadProtocol(str, Enum):
    """Protocol used for downloading remote files."""
    
    FTP = "ftp"
    FTPS = "ftps"  # FTP over TLS (e.g., CDDIS)
    HTTP = "http"
    HTTPS = "https"


class ProductQuality(str, Enum):
    """Enum for product quality levels."""

    FINAL = "FIN"
    RAPID = "RAP"
    REAL_TIME_STREAMING = "RTS"


class ConstellationCode(str, Enum):
    GPS = "n"
    GLONASS = "g"


@dataclass
class ResourceQueryResult:
    """
    Unified base result for all resource queries.
    
    Provides a standardized interface for identifying the download protocol
    and constructing the full URL for any GNSS product resource.
    
    Attributes
    ----------
    server : str
        Server hostname or URL (e.g., ``ftp://igs.gnsswhu.cn`` or ``https://files.igs.org``).
    directory : str
        Remote directory path.
    filename : str
        Remote filename.
    protocol : DownloadProtocol
        The protocol to use for downloading (FTP, FTPS, HTTP, HTTPS).
    """
    
    server: str
    directory: str
    filename: str
    protocol: DownloadProtocol = DownloadProtocol.FTP
    
    @property
    def url(self) -> str:
        """Full URL to the remote file."""
        host = self.server.rstrip("/")
        path = self.directory.strip("/")
        return f"{host}/{path}/{self.filename}"
    
    @property
    def is_http(self) -> bool:
        """True if this resource should be downloaded via HTTP/HTTPS."""
        return self.protocol in (DownloadProtocol.HTTP, DownloadProtocol.HTTPS)
    
    @property
    def is_ftp(self) -> bool:
        """True if this resource should be downloaded via FTP/FTPS."""
        return self.protocol in (DownloadProtocol.FTP, DownloadProtocol.FTPS)
    
    @property
    def requires_tls(self) -> bool:
        """True if this resource requires TLS encryption (HTTPS or FTPS)."""
        return self.protocol in (DownloadProtocol.HTTPS, DownloadProtocol.FTPS)


@dataclass
class FTPFileResult(ResourceQueryResult):
    """
    The result of a successful FTP file query.

    Attributes
    ----------
    server:
        FTP host URL, e.g. ``ftp://igs.gnsswhu.cn``.
    directory:
        Remote directory path (without leading slash), e.g.
        ``pub/whu/phasebias/2025/orbit``.
    filename:
        Remote filename, e.g.
        ``WMC0DEMFIN_20253050000_01D_05M_ORB.SP3.gz``.
    quality:
        The quality level at which the file was found.
    protocol:
        Download protocol (defaults to FTP).
    """

    quality: ProductQuality = field(default=ProductQuality.FINAL)
    protocol: DownloadProtocol = field(default=DownloadProtocol.FTP)

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



class ProductDirectorySourceFTP(ABC,BaseModel):
    ftpserver: str
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
            "sp3",
            "orbit",
            "clk",
            "sum",
            "bias",
            "erp",
            "obx",
        ],
        quality: ProductQuality,
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
