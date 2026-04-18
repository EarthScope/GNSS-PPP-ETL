import os
import subprocess
from datetime import datetime

import fsspec
import requests
from gnss_product_management.environments.gnss_station_network import GNSSStation, NetworkProtocol


class EarthScopeProtocol(NetworkProtocol):
    id = "ERT"
    url = "https://web-services.unavco.org/events/event_response/radius_search/beta?lat={lat}&lon={lon}&date={date}&radius={radius_m}"

    def radius_spatial_query(
        self, date: datetime, lat: float, lon: float, radius_km: float
    ) -> list[GNSSStation] | None:
        date_str = date.strftime("%Y-%m-%d")
        radius_m = radius_km * 1000
        url = self.url.format(lat=lat, lon=lon, date=date_str, radius_m=radius_m)
        response = requests.get(url)
        match response.status_code:
            case 200:
                return self.parse_spatial_query_response(response)
            case _:
                return None

    def parse_spatial_query_response(self, response: requests.Response) -> list[GNSSStation] | None:
        if response.status_code != 200:
            return None
        data = response.json()
        stations = []
        for record in data:
            try:
                station = GNSSStation(
                    site_code=record["station_code"],
                    lat=record["lat"],
                    lon=record["lon"],
                    network_id=self.id,
                    end_date=datetime.fromisoformat(record["latest_data_from_search"]),
                    data_center=self.id,
                )
                stations.append(station)
            except KeyError:
                continue
        return stations

    def filesystem(self) -> "fsspec.AbstractFileSystem | None":
        token = os.environ.get("EARTHSCOPE_TOKEN")
        if token is None:
            try:
                from earthscope_sdk.client import EarthScopeClient

                client = EarthScopeClient()
                token = client.ctx.device_code_flow.access_token
            except Exception:
                return None
        return fsspec.filesystem(
            "https", headers={"Authorization": f"Bearer {token}"}, skip_instance_cache=True
        )

    def login(self) -> str | None:
        subprocess.run("es login", shell=True, check=True)
        subprocess.run(
            "export ES_OAUTH2__REFRESH_TOKEN=${es user get-refresh-token}", shell=True, check=True
        )
