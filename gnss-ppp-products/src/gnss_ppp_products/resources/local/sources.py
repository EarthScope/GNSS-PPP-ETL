
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
from .base import _date_to_gps_week, _parse_date,_date_to_gps_week_day,_date_to_year_doy

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
    
    def query(self, date: datetime.datetime | datetime.date, mission: str, product: str) -> Path:
        """Construct the expected local path for a given product."""
        # For simplicity, we assume all products are stored in gps_week_day_directory
        return self.gps_week_day_directory(date) / f"{mission}_{product}_{date.strftime('%Y%m%d')}.dat"