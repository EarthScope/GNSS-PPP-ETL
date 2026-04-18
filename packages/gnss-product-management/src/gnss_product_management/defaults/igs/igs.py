import datetime 
from pathlib import Path
from typing import Annotated
import json
import numpy as np
from pydantic import BaseModel, Field
from haversine import haversine
from shapely import STRtree,Point
from gnss_product_management.environments.gnss_station_network import GNSSStation, NetworkProtocol


class IGSAgency(BaseModel):
    id: int
    name: str
    shortname: str
    country: str


class IGSNetwork(BaseModel):
    id: int
    name: str


class IGSTideGauge(BaseModel):
    name: str
    link: str
    distance: int  # metres from station


# Three-element coordinate vectors
XYZTuple = Annotated[list[float], Field(min_length=3, max_length=3)]
LLHTuple = Annotated[list[float], Field(min_length=3, max_length=3)]
UNETuple = Annotated[list[float], Field(min_length=3, max_length=3)]


class IGSStation(BaseModel):
    """Raw record from the IGS Network API (one element of the stations list)."""

    # ── Identity ──────────────────────────────────────────────────────
    name: str = Field(description="9-character IGS long name, e.g. 'ABMF00GLP'")
    status: int = Field(description="Station status code (3=inactive, 4=active)")
    domes_number: str

    # ── Membership ───────────────────────────────────────────────────
    agencies: list[IGSAgency]
    networks: list[IGSNetwork]
    join_date: datetime.date | None = None

    # ── Position ─────────────────────────────────────────────────────
    xyz: XYZTuple = Field(description="ECEF coordinates [X, Y, Z] in metres")
    llh: LLHTuple = Field(
        description="Geodetic coordinates [lat, lon, height] in deg/deg/m"
    )

    # ── Location ─────────────────────────────────────────────────────
    city: str
    state: str
    country: str = Field(description="ISO 3166-1 alpha-2 country code")

    # ── Equipment ────────────────────────────────────────────────────
    antenna_type: str
    antenna_serial_number: str
    antenna_marker_une: UNETuple = Field(
        description="Antenna offset [up, north, east] in metres"
    )
    radome_type: str
    antcal: str | None = None
    receiver_type: str
    serial_number: str
    firmware: str
    frequency_standard: str | None = None

    # ── Data availability ────────────────────────────────────────────
    satellite_system: list[str] = Field(
        description="Tracked constellations, e.g. ['GPS', 'GLO']"
    )
    real_time_systems: list[str]
    data_center: str | None = None
    last_publish: datetime.datetime
    last_rinex2: datetime.date | None = None
    last_rinex3: datetime.date | None = None
    last_rinex4: datetime.date | None = None
    last_data_time: datetime.date | None = None
    last_data: int | None = Field(
        default=None,
        description="Days since last data was received",
    )

    # ── Nearby infrastructure ────────────────────────────────────────
    tide_gauges: list[IGSTideGauge] = Field(default_factory=list)

    # ── Derived helpers ──────────────────────────────────────────────

    @property
    def site_code(self) -> str:
        """4-character lowercase station identifier (first 4 chars of *name*)."""
        return self.name[:4].lower()

    @property
    def lat(self) -> float:
        return self.llh[0]

    @property
    def lon(self) -> float:
        return self.llh[1]

    @property
    def height_m(self) -> float:
        return self.llh[2]

    @property
    def rinex_versions(self) -> list[str]:
        """RINEX versions for which recent data exists."""
        return [
            v
            for v, date in (
                ("2", self.last_rinex2),
                ("3", self.last_rinex3),
                ("4", self.last_rinex4),
            )
            if date is not None
        ]

    @property
    def is_active(self) -> bool:
        return self.status == 4

class IGSStationCollection(BaseModel):
    stations: list[IGSStation]

    @classmethod
    def from_json(cls, path: Path) -> "IGSStationCollection":
        with open(path, "r") as f:
            data = json.load(f)
        return cls.model_validate({"stations": data})
    
    def within(self, lat: float, lon: float, radius_km: float) -> "IGSStationCollection":
        """Return subset of stations within *radius_km* of the given point."""

        center = (lat, lon)
        matches = []
        for s in self.stations:
            dist_km = haversine(center, (s.lat, s.lon))

            if dist_km <= radius_km:
                matches.append(s)
        return IGSStationCollection(stations=matches)

class IGSProtocol(NetworkProtocol):
    id = "IGS"

    def __init__(self, catalog_path: Path | None = None) -> None:
        if catalog_path is None:
            catalog_path = Path(__file__).parent / "igs_stations.json"
        self._index = IGSStationCollection.from_json(catalog_path)
        self.rtree = STRtree([Point(s.lon, s.lat) for s in self._index.stations])

    def _within(self, lat: float, lon: float, radius_km: float) -> list[IGSStation]:
        """Return subset of stations within *radius_km* of the given point."""
        center = Point(lon, lat)
        km_to_deg  = 111 * np.cos(np.radians(lat))  # rough conversion factor at given latitude

        buffer = center.buffer(radius_km / km_to_deg) 
        matches:np.ndarray = self.rtree.query(buffer)
        stations = [self._index.stations[idx] for idx in matches.tolist()] or []
        return stations

        
    def radius_spatial_query(  # noqa: ARG002
        self, date: datetime.datetime, lat: float, lon: float, radius_km: float
    ) -> list[GNSSStation] | None:
        matches = self._within(lat, lon, radius_km)
        return [
            GNSSStation(
                site_code=rec.site_code,
                lat=rec.lat,
                lon=rec.lon,
                network_id="IGS",
                data_center=rec.data_center,
            )
            for rec in matches
        ]
