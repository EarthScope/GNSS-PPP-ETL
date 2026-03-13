"""
Local Resource Base Classes
============================

Provides base classes for local file resources that mirror the interface
of remote resources, enabling unified file access patterns.

Directory Organization Strategies
---------------------------------
    - **PRIDE**: ``{year}/{doy}/`` for daily, ``{year}/product/common/`` for common
    - **GPS_WEEK**: ``{gps_week}/`` 
    - **YEAR_DOY**: ``{year}/{doy}/``
    - **YEAR_MONTH**: ``{year}/{month:02d}/``

Usage
-----
    >>> from gnss_ppp_products.resources.local import LocalProductStore
    >>> store = LocalProductStore(base_dir="/data/gnss")
    >>> result = store.query_orbit(date=datetime.date(2025, 1, 15))
    >>> print(result.path)
    /data/gnss/2025/product/common/WMC0DEMFIN_20250150000_01D_05M_ORB.SP3.gz
"""

from abc import ABC, abstractmethod
import datetime
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple, Union
import re
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Temporal Utilities
# ---------------------------------------------------------------------------

GNSS_START_TIME = datetime.datetime(1980, 1, 6, tzinfo=datetime.timezone.utc)


def _parse_date(date: Union[datetime.date, datetime.datetime]) -> Tuple[str, str]:
    """Return (year, doy) as zero-padded strings."""
    if isinstance(date, datetime.datetime):
        date = date.date()
    year = str(date.year)
    doy = f"{date.timetuple().tm_yday:03d}"
    return year, doy


def _date_to_gps_week(date: Union[datetime.date, datetime.datetime]) -> int:
    """Return GPS week number for the given date."""
    if isinstance(date, datetime.datetime):
        date = date.date()
    time_since_epoch = date - GNSS_START_TIME.date()
    return time_since_epoch.days // 7


def _date_to_gps_week_day(date: Union[datetime.date, datetime.datetime]) -> Tuple[int, int]:
    """Return (GPS week, day of week 0-6) for the given date."""
    if isinstance(date, datetime.datetime):
        date = date.date()
    time_since_epoch = date - GNSS_START_TIME.date()
    gps_week = time_since_epoch.days // 7
    day_of_week = time_since_epoch.days % 7
    return gps_week, day_of_week

def _date_to_year_doy(date: Union[datetime.date, datetime.datetime]) -> Tuple[int, int]:

    doy = date.timetuple().tm_yday
    return date.year, doy

# ---------------------------------------------------------------------------
# Directory Organization Strategies
# ---------------------------------------------------------------------------


class DirectoryStrategy(str, Enum):
    """Directory organization strategies for local file storage."""
    
    PRIDE = "pride"           # {year}/{doy}/ and {year}/product/common/
    GPS_WEEK = "gps_week"     # {gps_week}/
    YEAR_DOY = "year_doy"     # {year}/{doy}/
    YEAR_MONTH = "year_month" # {year}/{month}/
    FLAT = "flat"             # No temporal organization


class ProductCategory(str, Enum):
    """Category of GNSS product for directory placement."""
    
    COMMON = "common"     # Orbit, clock, bias - goes in common/
    DAILY = "daily"       # Navigation, rinex - goes in daily/
    STATIC = "static"     # ANTEX, tables - date-independent
    ATMOSPHERIC = "atmos" # Troposphere, ionosphere


# ---------------------------------------------------------------------------
# Local Query Results
# ---------------------------------------------------------------------------


@dataclass
class LocalFileResult:
    """
    Result of a local file query.
    
    Mirrors the interface of remote ResourceQueryResult but for local files.
    
    Attributes
    ----------
    base_dir : Path
        Root directory of the local store.
    directory : str
        Relative directory path within base_dir.
    filename : str
        Filename.
    category : ProductCategory
        Product category (for directory placement hints).
    """
    
    base_dir: Path
    directory: str
    filename: str
    category: ProductCategory = ProductCategory.COMMON
    
    @property
    def path(self) -> Path:
        """Full absolute path to the file."""
        return self.base_dir / self.directory / self.filename
    
    @property
    def relative_path(self) -> Path:
        """Path relative to base_dir."""
        return Path(self.directory) / self.filename
    
    @property
    def exists(self) -> bool:
        """True if the file exists on disk."""
        return self.path.exists()
    
    @property
    def url(self) -> str:
        """File URL (for compatibility with remote interface)."""
        return f"file://{self.path}"
    
    def __str__(self) -> str:
        return str(self.path)


@dataclass
class LocalOrbitClockResult(LocalFileResult):
    """Result for orbit/clock product queries."""
    
    quality: str = "FIN"
    product_type: str = "sp3"  # sp3, clk, erp, bias, obx


@dataclass
class LocalNavigationResult(LocalFileResult):
    """Result for navigation file queries."""
    
    rinex_version: int = 3
    constellation: str = "M"  # M=mixed, G=GPS, R=GLONASS


@dataclass
class LocalAntexResult(LocalFileResult):
    """Result for ANTEX file queries."""
    
    frame_type: Optional[str] = None


@dataclass
class LocalAtmosphericResult(LocalFileResult):
    """Result for atmospheric (tropo/iono) file queries."""
    
    product_type: str = "ion"  # ion, vmf, orography


# ---------------------------------------------------------------------------
# Directory Builder
# ---------------------------------------------------------------------------


class LocalDirectoryBuilder:
    """
    Builds temporal directory paths based on strategy.
    
    Parameters
    ----------
    base_dir : Path
        Root directory for local storage.
    strategy : DirectoryStrategy
        Organization strategy to use.
    
    Examples
    --------
    >>> builder = LocalDirectoryBuilder(Path("/data/gnss"), DirectoryStrategy.PRIDE)
    >>> builder.common_dir(datetime.date(2025, 1, 15))
    PosixPath('/data/gnss/2025/product/common')
    >>> builder.daily_dir(datetime.date(2025, 1, 15))
    PosixPath('/data/gnss/2025/015')
    """
    
    def __init__(self, base_dir: Path, strategy: DirectoryStrategy = DirectoryStrategy.PRIDE):
        self.base_dir = Path(base_dir)
        self.strategy = strategy
    
    def common_dir(self, date: datetime.date, create: bool = False) -> Path:
        """
        Directory for common products (orbit, clock, bias).
        
        Parameters
        ----------
        date : datetime.date
            Date for temporal organization.
        create : bool
            If True, create directory if it doesn't exist.
        """
        path = self._build_common_path(date)
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path
    
    def daily_dir(self, date: datetime.date, create: bool = False) -> Path:
        """
        Directory for daily products (navigation, rinex).
        
        Parameters
        ----------
        date : datetime.date
            Date for temporal organization.
        create : bool
            If True, create directory if it doesn't exist.
        """
        path = self._build_daily_path(date)
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path
    
    def static_dir(self, create: bool = False) -> Path:
        """
        Directory for static files (ANTEX, tables).
        
        These files are not date-organized.
        """
        path = self.base_dir / "static"
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path
    
    def atmospheric_dir(self, date: datetime.date, create: bool = False) -> Path:
        """Directory for atmospheric products (VMF, ionosphere)."""
        year, doy = _parse_date(date)
        path = self.base_dir / year / "atmosphere" / doy
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path
    
    def _build_common_path(self, date: datetime.date) -> Path:
        year, doy = _parse_date(date)
        
        if self.strategy == DirectoryStrategy.PRIDE:
            return self.base_dir / year / "product" / "common"
        elif self.strategy == DirectoryStrategy.GPS_WEEK:
            gps_week = _date_to_gps_week(date)
            return self.base_dir / str(gps_week)
        elif self.strategy == DirectoryStrategy.YEAR_DOY:
            return self.base_dir / year / doy
        elif self.strategy == DirectoryStrategy.YEAR_MONTH:
            month = f"{date.month:02d}"
            return self.base_dir / year / month
        else:  # FLAT
            return self.base_dir
    
    def _build_daily_path(self, date: datetime.date) -> Path:
        year, doy = _parse_date(date)
        
        if self.strategy == DirectoryStrategy.PRIDE:
            return self.base_dir / year / doy
        elif self.strategy == DirectoryStrategy.GPS_WEEK:
            gps_week, dow = _date_to_gps_week_day(date)
            return self.base_dir / str(gps_week)
        elif self.strategy == DirectoryStrategy.YEAR_DOY:
            return self.base_dir / year / doy
        elif self.strategy == DirectoryStrategy.YEAR_MONTH:
            month = f"{date.month:02d}"
            return self.base_dir / year / month / doy
        else:  # FLAT
            return self.base_dir
    
    def relative_path(self, full_path: Path) -> str:
        """Return path relative to base_dir as string."""
        try:
            return str(full_path.relative_to(self.base_dir))
        except ValueError:
            return str(full_path)


# ---------------------------------------------------------------------------
# File Finder
# ---------------------------------------------------------------------------


class LocalFileFinder:
    """
    Finds files in local directories using regex patterns.
    
    Parameters
    ----------
    directory : Path
        Directory to search in.
    
    Examples
    --------
    >>> finder = LocalFileFinder(Path("/data/gnss/2025/product/common"))
    >>> finder.find_matching(r"WMC.*FIN.*SP3.*")
    [PosixPath('/data/gnss/2025/product/common/WMC0DEMFIN_20250150000_01D_05M_ORB.SP3.gz')]
    """
    
    def __init__(self, directory: Path):
        self.directory = Path(directory)
    
    def find_matching(
        self,
        pattern: str,
        recursive: bool = False,
    ) -> List[Path]:
        """
        Find files matching a regex pattern.
        
        Parameters
        ----------
        pattern : str
            Regex pattern to match filenames.
        recursive : bool
            If True, search subdirectories.
        
        Returns
        -------
        List[Path]
            List of matching file paths, sorted by name.
        """
        if not self.directory.exists():
            return []
        
        regex = re.compile(pattern, re.IGNORECASE)
        matches = []
        
        if recursive:
            for path in self.directory.rglob("*"):
                if path.is_file() and regex.search(path.name):
                    matches.append(path)
        else:
            for path in self.directory.iterdir():
                if path.is_file() and regex.search(path.name):
                    matches.append(path)
        
        return sorted(matches, key=lambda p: p.name)
    
    def find_best_match(
        self,
        pattern: str,
        prefer_newest: bool = True,
    ) -> Optional[Path]:
        """
        Find the best matching file.
        
        Parameters
        ----------
        pattern : str
            Regex pattern to match filenames.
        prefer_newest : bool
            If True, return the file with the newest modification time.
        
        Returns
        -------
        Optional[Path]
            Best matching file, or None if no match.
        """
        matches = self.find_matching(pattern)
        if not matches:
            return None
        
        if prefer_newest:
            return max(matches, key=lambda p: p.stat().st_mtime)
        return matches[-1]  # Last alphabetically (often contains highest version)
    
    def list_all(self) -> List[str]:
        """List all filenames in the directory."""
        if not self.directory.exists():
            return []
        return sorted([f.name for f in self.directory.iterdir() if f.is_file()])


# ---------------------------------------------------------------------------
# Abstract Base for Local Sources
# ---------------------------------------------------------------------------


class LocalProductSource(ABC):
    """
    Abstract base class for local product sources.
    
    Provides the same query interface as remote sources, but for local files.
    
    Parameters
    ----------
    base_dir : Path
        Root directory for local storage.
    strategy : DirectoryStrategy
        Directory organization strategy.
    """
    
    def __init__(
        self,
        base_dir: Union[str, Path],
        strategy: DirectoryStrategy = DirectoryStrategy.PRIDE,
    ):
        self.base_dir = Path(base_dir)
        self.strategy = strategy
        self.dir_builder = LocalDirectoryBuilder(self.base_dir, strategy)
    
    @abstractmethod
    def query(self, date: datetime.date, **kwargs) -> Optional[LocalFileResult]:
        """
        Query for a local file matching the given date and parameters.
        
        Parameters
        ----------
        date : datetime.date
            Processing date.
        **kwargs
            Additional query parameters (product type, quality, etc.)
        
        Returns
        -------
        Optional[LocalFileResult]
            Result pointing to the local file, or None if not found.
        """
        pass
    
    def ensure_directory(self, date: datetime.date, category: ProductCategory) -> Path:
        """
        Ensure the appropriate directory exists for the given date and category.
        
        Returns the directory path.
        """
        if category == ProductCategory.COMMON:
            return self.dir_builder.common_dir(date, create=True)
        elif category == ProductCategory.DAILY:
            return self.dir_builder.daily_dir(date, create=True)
        elif category == ProductCategory.STATIC:
            return self.dir_builder.static_dir(create=True)
        elif category == ProductCategory.ATMOSPHERIC:
            return self.dir_builder.atmospheric_dir(date, create=True)
        else:
            return self.dir_builder.daily_dir(date, create=True)
