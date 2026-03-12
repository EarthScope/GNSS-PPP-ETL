from pathlib import Path
from datetime import datetime
from sys import prefix
from typing import Union
from ..assets.utils.date_utils import parse_date,date_to_gps_week
from ..assets.base import ProductFileFormat,ProductContentType

class StaticDirectory:
    """Provides a static directory path for GNSS PPP products."""
    prefix = "static"
    def __init__(self, parent: Union[str, Path]):
        """
        Initialize with a static path.
        
        Args:
            parent: The static directory path
        """        
        self.path = Path(parent) / self.prefix
        self.path.mkdir(parents=True, exist_ok=True)  # Ensure the directory exists
        self.atx: Path = self.path / "atx"
        self.atx.mkdir(parents=True, exist_ok=True)  # Ensure the atx directory exists
        self.ocean: Path = self.path / "ocean"
        self.ocean.mkdir(parents=True, exist_ok=True)  # Ensure the ocean directory exists
        self.atmosphere: Path = self.path / "atmosphere"
        self.atmosphere.mkdir(parents=True, exist_ok=True)  # Ensure the atmosphere directory exists
        self.tables: Path = self.path / "tables"
        self.tables.mkdir(parents=True, exist_ok=True)  # Ensure the tables directory exists

class ProductDirectory:
    prefix = "products"
    def __init__(self,parent: Union[str, Path]):
        self.path = Path(parent) / self.prefix
        self.path.mkdir(parents=True, exist_ok=True)  # Ensure the directory exists

    def common(self, date: datetime) -> Path:
        """Build a common directory path for a given date and product type."""
        year, doy = parse_date(date)
        folder = self.path / str(year) / f"{doy:03d}" / "common"
        folder.mkdir(parents=True, exist_ok=True)  # Ensure the directory exists
        return folder

class RinexDirectory:
    prefix = "rinex"
    def __init__(self,parent: Union[str, Path]):
        self.path = Path(parent) / self.prefix
        self.path.mkdir(parents=True, exist_ok=True)  # Ensure the directory exists

    def rinex(self, date: datetime) -> Path:
        """Build a Rinex directory path for a given date."""
        year, doy = parse_date(date)
        folder = self.path / str(year) / f"{doy:03d}"
        folder.mkdir(parents=True, exist_ok=True)  # Ensure the directory exists
        return folder
        
class BaseDirectory:
    """Base directory structure for GNSS PPP products."""
    def __init__(self, parent: Union[str, Path]):
        self.path = Path(parent)
        self.path.mkdir(parents=True, exist_ok=True)  # Ensure the base directory exists
        self.static = StaticDirectory(self.path)
        self.products = ProductDirectory(self.path)
        self.rinex = RinexDirectory(self.path)
    
   