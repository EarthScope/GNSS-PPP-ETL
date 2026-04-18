import datetime
from pathlib import Path

import numpy as np
import yaml
from shapely import STRtree, Point

from gnss_product_management.environments.gnss_station_network import (
    GNSSStation,
    NetworkProtocol,
)


class RBMCProtocol(NetworkProtocol):
    """Spatial query protocol for the Brazilian RBMC network.

    Loads station coordinates from the bundled ``rbmc_stations.yaml``
    catalog (sourced from the IBGE RBMC_2024.kmz) and performs
    point-radius queries using a Shapely STRtree.

    No authentication is required — RBMC data is freely accessible via
    HTTPS at geoftp.ibge.gov.br.
    """

    id = "RBMC"

    def __init__(self, catalog_path: Path | None = None) -> None:
        if catalog_path is None:
            from gpm_specs.configs import NETWORKS_RESOURCE_DIR
            catalog_path = Path(NETWORKS_RESOURCE_DIR) / "rbmc_stations.yaml"

        with open(catalog_path) as f:
            data = yaml.safe_load(f)

        self._stations: list[dict] = data["stations"]
        self._rtree = STRtree([Point(s["lon"], s["lat"]) for s in self._stations])

    def _within(self, lat: float, lon: float, radius_km: float) -> list[dict]:
        center = Point(lon, lat)
        km_to_deg = 111 * np.cos(np.radians(lat))
        buffer = center.buffer(radius_km / km_to_deg)
        matches: np.ndarray = self._rtree.query(buffer)
        return [self._stations[i] for i in matches.tolist()]

    def radius_spatial_query(
        self,
        date: datetime.datetime,
        lat: float,
        lon: float,
        radius_km: float,
    ) -> list[GNSSStation] | None:
        return [
            GNSSStation(
                site_code=s["site_code"],
                lat=s["lat"],
                lon=s["lon"],
                network_id="RBMC",
                data_center=s.get("server_id", "RBMC_IBGE"),
            )
            for s in self._within(lat, lon, radius_km)
        ]
