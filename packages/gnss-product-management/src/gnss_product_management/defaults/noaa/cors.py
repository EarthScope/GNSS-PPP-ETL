from datetime import datetime
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point

from gnss_product_management.environments.gnss_station_network import GNSSStation, NetworkProtocol

_CSV_NAME = "NOAA CORS Network (sm scale).csv"


class NOAA_CORSCollection:
    """NOAA CORS station collection backed by the NGS CSV export."""

    def __init__(self, path: Path | None = None) -> None:
        if path is None:
            path = Path(__file__).parent / _CSV_NAME
        self.gdf = self._load(path)

    @staticmethod
    def _load(path: Path) -> gpd.GeoDataFrame:
        df = pd.read_csv(path, encoding="utf-8-sig")
        df["START_DATE"] = pd.to_datetime(df["START_DATE"], format="%m/%d/%Y", errors="coerce")
        geometry = [Point(x, y) for x, y in zip(df["x"], df["y"])]
        return gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")


class NOAACORSProtocol(NetworkProtocol):
    id = "CORS"

    def __init__(self) -> None:

        self._index = NOAA_CORSCollection()

    def _within(self, lat: float, lon: float, radius_km: float) -> list[GNSSStation]:
        center = Point(lon, lat)
        km_to_deg = 111 * np.cos(np.radians(lat))  # rough conversion factor at given latitude

        buffer = center.buffer(radius_km / km_to_deg)
        matches = self._index.gdf[self._index.gdf.geometry.within(buffer)]
        return [
            GNSSStation(
                site_code=rec["SITEID"].lower(),
                lat=rec["y"],
                lon=rec["x"],
                network_id=self.id,
            )
            for _, rec in matches.iterrows()
        ]

    def radius_spatial_query(
        self, date: datetime, lat: float, lon: float, radius_km: float
    ) -> list[GNSSStation] | None:
        matches = self._within(lat, lon, radius_km)
        return matches
