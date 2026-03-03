from __future__ import annotations
import datetime 
from pydantic import Field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple
import yaml
from enum import Enum
import dagster as dg


# Path to the sources.yml in this repository
# product_sources.py lives at: <project>/src/gnss_ppp_products/utils/
# sources.yml lives at:        <project>/config/sources.yml
_SOURCES_YML = (
    Path(__file__).resolve().parent.parent.parent.parent / "config" / "sources.yml"
)

GNSS_START_TIME = datetime.datetime(
    1980, 1, 6, tzinfo=datetime.timezone.utc
)  # GNSS start time


def _load_sources_yaml() -> Dict[str, Any]:
    if not _SOURCES_YML.is_file():
        raise FileNotFoundError(f"sources.yml not found at {_SOURCES_YML}")
    with _SOURCES_YML.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def _parse_date(date: datetime.date | datetime.datetime) -> Tuple[str, str]:
    """
    Parse a date or datetime object and return the year and day of year (DOY) as strings.
    Args:
        date (datetime.date | datetime.datetime): The date or datetime object to parse.
    Returns:
        Tuple[str, str]: A tuple containing the year and the day of year (DOY) as strings.
    """

    if isinstance(date, datetime.datetime):
        date = date.date()
    year = str(date.year)
    doy = date.timetuple().tm_yday
    if doy < 10:
        doy = f"00{doy}"
    elif doy < 100:
        doy = f"0{doy}"
    doy = str(doy)
    return year, doy


def _date_to_gps_week(date: datetime.date | datetime.datetime) -> int:
    """
    Convert a given date to the corresponding GPS week number.

    The GPS week number is calculated as the number of weeks since the start of the GPS epoch (January 6, 1980).

    Args:
        date (datetime.date | datetime.datetime): The date to be converted. Can be either a datetime.date or datetime.datetime object.

    Returns:
        int: The GPS week number corresponding to the given date.
    """
    # get the number of weeks since the start of the GPS epoch

    if isinstance(date, datetime.datetime):
        date = date.date()
    time_since_epoch = date - GNSS_START_TIME.date()
    gps_week = time_since_epoch.days // 7
    return gps_week


class ProductQuality(str,Enum):
    """Enum for product quality levels."""
    FINAL = "FIN"
    RAPID = "RAP"
    REAL_TIME_STREAMING = "RTS"

class ConstellationCode(str,Enum):
    GPS = "n"
    GLONASS = "g"

class ProductFileSourceRegex:
    def __init__(self,
        product_sp3: str,
        product_obx: str,
        product_clk: str,
        product_erp: str,
        product_sum: str,
        product_bias: str,
        product_broadcast_rnx3: str,
        product_broadcast_rnx2: str,
    ):
        self.product_sp3: str = product_sp3
        self.product_obx: str = product_obx
        self.product_clk: str = product_clk
        self.product_erp: str = product_erp
        self.product_sum: str = product_sum
        self.product_bias: str = product_bias
        self.product_broadcast_rnx3: str = product_broadcast_rnx3
        self.product_broadcast_rnx2: str = product_broadcast_rnx2

    def sp3(self,date: datetime.date | datetime.datetime,quality: ProductQuality) -> str:
        year, doy = _parse_date(date)
        return self.product_sp3.format(quality=quality.value,year=year,doy=doy)
    
    def obx(self,date: datetime.date | datetime.datetime,quality: ProductQuality) -> str:
        year, doy = _parse_date(date)
        return self.product_obx.format(quality=quality.value,year=year,doy=doy)
    
    def clk(self,date: datetime.date | datetime.datetime,quality: ProductQuality) -> str:
        year, doy = _parse_date(date)
        return self.product_clk.format(quality=quality.value,year=year,doy=doy)
    
    def erp(self,date: datetime.date | datetime.datetime,quality: ProductQuality) -> str:
        year, doy = _parse_date(date)
        return self.product_erp.format(quality=quality.value,year=year,doy=doy)

    def sum(self,date: datetime.date | datetime.datetime,quality: ProductQuality) -> str:
        year, doy = _parse_date(date)
        return self.product_sum.format(quality=quality.value,year=year,doy=doy)

    def bias(self,date: datetime.date | datetime.datetime,quality: ProductQuality) -> str:
        year, doy = _parse_date(date)
        return self.product_bias.format(quality=quality.value,year=year,doy=doy)
    
    def broadcast_rnx3(self,date: datetime.date | datetime.datetime) -> str:
        year, doy = _parse_date(date)
        yy = str(year)[2:4]
        return self.product_broadcast_rnx3.format(year=year,doy=doy)
    
    def broadcast_rnx2(self,date: datetime.date | datetime.datetime,constellation: ConstellationCode) -> str:
        year, doy = _parse_date(date)
        yy = str(year)[2:4]
        return self.product_broadcast_rnx2.format(doy=doy,yy=yy,constellation=constellation.value)

class ProductDirectorySourceFTP:

    def __init__(self,
        ftpserver: str,
        rinex_nav: Optional[str] = None,
        product_sp3: Optional[str] = None,
        product_clk: Optional[str] = None,
        product_sum: Optional[str] = None,
        product_bias: Optional[str] = None,
        product_erp: Optional[str] = None,
        product_obx: Optional[str] = None,
    ):
         self.ftpserver = ftpserver
         self.rinex_nav = rinex_nav
         self.product_sp3 = product_sp3
         self.product_clk = product_clk
         self.product_sum = product_sum
         self.product_bias = product_bias
         self.product_erp = product_erp
         self.product_obx = product_obx

    @classmethod
    def from_config(cls,ftpserver:str,directories:Mapping[str,str]) -> ProductDirectorySourceFTP:
        return cls(
            ftpserver=ftpserver,
            rinex_nav=directories.get("rinex_nav"),
            product_sp3=directories.get("product_sp3"),
            product_clk=directories.get("product_clk"),
            product_sum=directories.get("product_sum"),
            product_bias=directories.get("product_bias"),
            product_erp=directories.get("product_erp"),
            product_obx=directories.get("product_obx"),
        )
    
    def rinex_nav_directory(self,date: datetime.date | datetime.datetime) -> Optional[str]:
        if self.rinex_nav is None:
            return None
        year, doy = _parse_date(date)
        yy = str(year)[2:4]
        return self.rinex_nav.format(year=year,doy=doy,yy=yy)
    
    def product_sp3_directory(self,date: datetime.date | datetime.datetime) -> Optional[str]:
        if self.product_sp3 is None:
            return None
        year, doy = _parse_date(date)
        gps_week = _date_to_gps_week(date)
        return self.product_sp3.format(year=year,doy=doy,gps_week=gps_week)
    
    def product_clk_directory(self,date: datetime.date | datetime.datetime) -> Optional[str]:
        if self.product_clk is None:
            return None
        year, doy = _parse_date(date)
        gps_week = _date_to_gps_week(date)
        return self.product_clk.format(year=year,doy=doy,gps_week=gps_week)
    
    def product_sum_directory(self,date: datetime.date | datetime.datetime) -> Optional[str]:
        if self.product_sum is None:
            return None
        year, doy = _parse_date(date)
        gps_week = _date_to_gps_week(date)
        return self.product_sum.format(year=year,doy=doy,gps_week=gps_week)

    def product_bias_directory(self,date: datetime.date | datetime.datetime) -> Optional[str]:
        if self.product_bias is None:
            return None
        year, doy = _parse_date(date)
        gps_week = _date_to_gps_week(date)
        return self.product_bias.format(year=year,doy=doy,gps_week=gps_week)
    
    def product_erp_directory(self,date: datetime.date | datetime.datetime) -> Optional[str]:
        if self.product_erp is None:
            return None
        year, doy = _parse_date(date)
        gps_week = _date_to_gps_week(date)
        return self.product_erp.format(year=year,doy=doy,gps_week=gps_week)
    
    def product_obx_directory(self,date: datetime.date | datetime.datetime) -> Optional[str]:
        if self.product_obx is None:
            return None
        year, doy = _parse_date(date)
        gps_week = _date_to_gps_week(date)
        return self.product_obx.format(year=year,doy=doy,gps_week=gps_week)

class ProductSourcePathFTP(dg.Config):
    ftpserver: str = Field(
        description="FTP server URL for GNSS product source"
    )
    directory:str = Field(
        description="Directory path on the FTP server for the GNSS products"
    )
    file_regex: str = Field(
        description="Regex pattern for GNSS product files in the directory"
    )
    discovered_remote_path: Optional[str] = Field(
        default=None,
        description="Discovered remote file path on the FTP server after searching",
    )

class ProductSourceCollectionFTP(dg.Config):
    final: ProductSourcePathFTP = Field(
        description="Source paths for final GNSS products"
    )
    rapid: ProductSourcePathFTP = Field(
        description="Source paths for rapid GNSS products"
    )
    rts: ProductSourcePathFTP = Field(
        description="Source paths for real-time streaming GNSS products"
    )

    @classmethod
    def from_config(cls,
        regex_config: callable,
        directory:str,
        ftpserver:str,
        date: datetime.date | datetime.datetime
    ) -> "ProductSourceCollectionFTP":
        return cls(
            final=ProductSourcePathFTP(
                ftpserver=ftpserver,
                directory=directory,
                file_regex=regex_config(date,ProductQuality.FINAL),
            ),
            rapid=ProductSourcePathFTP(
                ftpserver=ftpserver,
                directory=directory,
                file_regex=regex_config(date,ProductQuality.RAPID),
            ),
            rts=ProductSourcePathFTP(
                ftpserver=ftpserver,
                directory=directory,
                file_regex=regex_config(date,ProductQuality.REAL_TIME_STREAMING),
            ),
        )

class Rinex2NavSourceFTP(dg.Config):
    gps: ProductSourcePathFTP = Field(
        description="Source path for GPS RINEX version 2 navigation files"
    )
    glonass: ProductSourcePathFTP = Field(
        description="Source path for GLONASS RINEX version 2 navigation files"
    )

class ProductSourcesFTP(dg.Config):
    date: datetime.date | datetime.datetime = Field(
        description="Date for which the product sources are valid"
    )
    sp3: ProductSourceCollectionFTP = Field(
        description="SP3 orbit product sources"
    )
    obx: ProductSourceCollectionFTP = Field(
        description="OBX quaternion product sources"
    )
    clk: ProductSourceCollectionFTP = Field(
        description="CLK clock product sources"
    )
    erp: ProductSourceCollectionFTP = Field(
        description="ERP earth rotation parameter product sources"
    )
    bias: ProductSourceCollectionFTP = Field(
        description="Code/phase bias product sources"
    )
    broadcast_rnx3: ProductSourcePathFTP = Field(
        description="Broadcast RINEX version 3 product sources"
    )
    broadcast_rnx2: Rinex2NavSourceFTP = Field(
        description="Broadcast RINEX version 2 product sources"
    )


def load_product_sources_FTP(date: datetime.date | datetime.datetime) -> Dict[str, ProductSourcesFTP]:
    """
    Load GNSS product sources from the sources.yml configuration file for a given date.

    Parameters:
    ----------- 
        date (datetime.date | datetime.datetime) 
            The date for which to load the product sources.
    Returns
    -------
        Dict[str, ProductSources]
            A dictionary mapping product types to their corresponding source paths.
    """
    source_map:Dict[str,ProductSourcesFTP] = {}
    config_dict:dict = _load_sources_yaml()
    regex_config: ProductFileSourceRegex = ProductFileSourceRegex(**config_dict["regex"])
    for name,source in config_dict["sources"].items():
        product_source_dirs = ProductDirectorySourceFTP.from_config(
            ftpserver=source["ftpserver"],
            directories=source.get("directories",{}),
        )
        if (directory:=product_source_dirs.product_sp3_directory(date)) is not None:
            
            sp3 = ProductSourceCollectionFTP.from_config(
                regex_config=regex_config.sp3,
                directory=directory,
                ftpserver=product_source_dirs.ftpserver,
                date=date,
            )

        if (directory:=product_source_dirs.product_obx_directory(date)) is not None:
            obx = ProductSourceCollectionFTP.from_config(
                regex_config=regex_config.obx,
                directory=directory,
                ftpserver=product_source_dirs.ftpserver,
                date=date,
            )
        if (directory:=product_source_dirs.product_clk_directory(date)) is not None:
            clk = ProductSourceCollectionFTP.from_config(
                regex_config=regex_config.clk,
                directory=directory,
                ftpserver=product_source_dirs.ftpserver,
                date=date,
            )
        if (directory:=product_source_dirs.product_erp_directory(date)) is not None:
            erp = ProductSourceCollectionFTP.from_config(
                regex_config=regex_config.erp,
                directory=directory,
            ftpserver=product_source_dirs.ftpserver,
            date=date,
        )
        if (directory:=product_source_dirs.product_bias_directory(date)) is not None:
            bias = ProductSourceCollectionFTP.from_config(
                regex_config=regex_config.bias,
                directory=directory,
                ftpserver=product_source_dirs.ftpserver,
                date=date,
            )
        if (directory := product_source_dirs.rinex_nav_directory(date)) is not None:
            broadcast_rnx3 = ProductSourcePathFTP(
                ftpserver=product_source_dirs.ftpserver,
                directory=directory,
                file_regex=regex_config.broadcast_rnx3(date),
            )
            broadcast_rnx2 = Rinex2NavSourceFTP(
                gps=ProductSourcePathFTP(
                    ftpserver=product_source_dirs.ftpserver,
                    directory=directory,
                    file_regex=regex_config.broadcast_rnx2(date,ConstellationCode.GPS),
                ),
                glonass=ProductSourcePathFTP(
                    ftpserver=product_source_dirs.ftpserver,
                    directory=directory,
                    file_regex=regex_config.broadcast_rnx2(date,ConstellationCode.GLONASS),
                ),
            )
        product_source_dir = ProductSourcesFTP(
            date=date,
            sp3=sp3,
            obx=obx,
            clk=clk,
            erp=erp,
            bias=bias,
            broadcast_rnx3=broadcast_rnx3,
            broadcast_rnx2=broadcast_rnx2,
        )
        source_map[name] = product_source_dir
    return source_map

class PrideFileStructure(dg.Config):
    daily: str = Field(
        description="Daily file structure pattern"
    )
    common: str = Field(
        description="Common file structure pattern"
    )
    @classmethod
    def from_date(cls,root_dir:Path,date: datetime.date | datetime.datetime) -> "PrideFileStructure":
        year, doy = _parse_date(date)
        return cls(
            daily=root_dir/f"{year}/{doy}/",
            common=root_dir/f"{year}/product/common/",
        )

class ProductSourcePathLocal(dg.Config):
    directory: Path = Field(
        description="Local directory path for GNSS products"
    )
    file_regex: str = Field(
        description="Regex pattern for GNSS product files in the directory"
    ) 

def find_local_product_source(
    product_sources_ftp: ProductSourcesFTP,
    product_sources_local:ProductSourcePathLocal,
    quality: ProductQuality,
) -> List[ProductSourcePathFTP]:
    """
    Find local GNSS product sources based on the provided FTP product sources and local directory.

    Parameters:
    -----------
        product_sources_ftp (ProductSourcesFTP): The GNSS product sources from FTP.
        product_sources_local (ProductSourcePathLocal): The local directory and file regex for GNSS products.
        quality (ProductQuality): The quality level of the products to find (e.g., FINAL, RAPID, RTS).

    Returns:
    --------
        List[ProductSourcePathFTP]: A list of local GNSS product source paths matching the specified quality.
    """
    local_sources:List[ProductSourcePathFTP] = []
    for product_name in ["sp3","obx","clk","erp"]:
        ftp_source_collection:ProductSourceCollectionFTP = getattr(product_sources_ftp,product_name)
        ftp_source_path:ProductSourcePathFTP = getattr(ftp_source_collection,quality.name.lower())
        matching_filenames = list(product_sources_local.directory.rglob(ftp_source_path.file_regex))
        if matching_filenames:
            local_sources.extend(matching_filenames)
    return local_sources    

if __name__ == "__main__":
    import datetime
    sources = load_product_sources_FTP(datetime.date(2024,6,15))
    import pprint
    pprint.pprint(sources)