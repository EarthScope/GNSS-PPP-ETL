
'''
Generic local directory structure:

/root
    /table - product table files (e.g. IGS products.txt, vienna mapping, orography, ocean loading)
    /year
        /gps_week - weekly products
            /doy - daily products (navigation files, ionosphere maps, VMF grids)


'''
import datetime
import logging
from pathlib import Path
from typing import Tuple
from .base import _date_to_gps_week, _parse_date,_date_to_gps_week_day,_date_to_year_doy
from ..products import types as product_types

class LocalDataSource:
    """Local data sources for GNSS PPP products."""

    def __init__(self, root_dir: str|Path) -> None:
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.table_dir = self.root_dir / "table"
        self.table_dir.mkdir(parents=True, exist_ok=True)

    def year_directory(self, date: datetime.datetime | datetime.date) -> Path:
        year_dir = self.root_dir / str(date.year)
        year_dir.mkdir(parents=True, exist_ok=True)
        return year_dir
    
    def gps_week_directory(self, date: datetime.datetime | datetime.date) -> Path:
        gps_week = _date_to_gps_week(date)
        week_dir = self.year_directory(date) / str(gps_week)
        week_dir.mkdir(parents=True, exist_ok=True)
        return week_dir
    
    def gps_week_day_directory(self, date: datetime.datetime | datetime.date) -> Path:
        _,doy = _date_to_year_doy(date)
        week_dir = self.gps_week_directory(date)
        week_day_dir = week_dir / f"{doy:03d}"
        week_day_dir.mkdir(parents=True, exist_ok=True)
        return week_day_dir
    
    def query(self, date: datetime.datetime | datetime.date, temporal_coverage: product_types.TemporalCoverage, regex: str) -> Tuple[Path, list[Path]] | None:
        """Construct the expected local path for a given product."""
        # For simplicity, we assume all products are stored in gps_week_day_directory
        match temporal_coverage:
            case product_types.TemporalCoverage.DAILY:
                dir_path = self.gps_week_day_directory(date)
            case product_types.TemporalCoverage.GPSWEEKLY:
                dir_path = self.gps_week_directory(date)
            case product_types.TemporalCoverage.YEARLY:
                dir_path = self.year_directory(date)
            case product_types.TemporalCoverage.EPOCH:
                dir_path = self.table_dir
            case _:
                raise ValueError(f"Unsupported temporal coverage: {temporal_coverage}")
        
        found_files = []
        # Search for files matching the regex in the directory
        for file in dir_path.glob(regex):
            if file.is_file():
                found_files.append(file)
        
        if not found_files:
            logging.info(f"No local files found in {dir_path} matching {regex}")
            return None
        # TODO - validate for complete/non-corrupted files, e.g. by checking file size or using checksums if available
        logging.info(f"Found local files in {dir_path} matching {regex}: {[str(f) for f in found_files]}")
        return dir_path,found_files
    
class PrideDataSource:
    """Local data source using the PRIDE directory structure."""
    
    def __init__(self,root_dir: str|Path,table_dir:str|Path) -> None:
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.table_dir = Path(table_dir)
        self.table_dir.mkdir(parents=True, exist_ok=True)

    def year_directory(self, date: datetime.datetime | datetime.date) -> Path:
        year_dir = self.root_dir / str(date.year)
        year_dir.mkdir(parents=True, exist_ok=True)
        return year_dir
    
    def doy_directory(self, date: datetime.datetime | datetime.date) -> Path:
        doy = date.timetuple().tm_yday
        doy_dir = self.year_directory(date) / f"{doy:03d}"
        doy_dir.mkdir(parents=True, exist_ok=True)
        return doy_dir
    
    def common_product_directory(self, date: datetime.datetime | datetime.date) -> Path:
        common_dir = self.year_directory(date) / "product" / "common"
        common_dir.mkdir(parents=True, exist_ok=True)
        return common_dir
    
    
