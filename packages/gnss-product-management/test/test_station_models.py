"""Tests for GNSSStation and SpatialFilter pure data models."""

from __future__ import annotations

import datetime

import pytest
from gnss_product_management.environments.gnss_station_network import (
    BoundingBox,
    GNSSStation,
    PointRadius,
)
from pydantic import ValidationError

# ── GNSSStation ───────────────────────────────────────────────────────


class TestGNSSStation:
    def test_required_fields(self) -> None:
        s = GNSSStation(site_code="FAIR", lat=64.978, lon=-147.499)
        assert s.site_code == "FAIR"
        assert s.lat == 64.978
        assert s.lon == -147.499

    def test_optional_fields_default_none(self) -> None:
        s = GNSSStation(site_code="FAIR", lat=64.978, lon=-147.499)
        assert s.network_id is None
        assert s.start_date is None
        assert s.end_date is None

    def test_optional_fields_set(self) -> None:
        s = GNSSStation(
            site_code="FAIR",
            lat=64.978,
            lon=-147.499,
            network_id="ERT",
            start_date=datetime.date(1993, 1, 1),
            end_date=datetime.date(2024, 12, 31),
        )
        assert s.network_id == "ERT"
        assert s.start_date == datetime.date(1993, 1, 1)
        assert s.end_date == datetime.date(2024, 12, 31)

    def test_missing_required_field_raises(self) -> None:
        with pytest.raises(ValidationError):
            GNSSStation(lat=64.978, lon=-147.499)  # type: ignore[call-arg]

    def test_round_trip(self) -> None:
        s = GNSSStation(site_code="WHIT", lat=60.751, lon=-135.224, network_id="ERT")
        assert GNSSStation.model_validate(s.model_dump()) == s


# ── PointRadius ───────────────────────────────────────────────────────


class TestPointRadius:
    def test_valid(self) -> None:
        p = PointRadius(lat=60.0, lon=-150.0, radius_km=100.0)
        assert p.lat == 60.0
        assert p.lon == -150.0
        assert p.radius_km == 100.0
        assert p.type == "point_radius"

    def test_zero_radius_raises(self) -> None:
        with pytest.raises(ValidationError, match="radius_km must be positive"):
            PointRadius(lat=60.0, lon=-150.0, radius_km=0.0)

    def test_negative_radius_raises(self) -> None:
        with pytest.raises(ValidationError, match="radius_km must be positive"):
            PointRadius(lat=60.0, lon=-150.0, radius_km=-10.0)

    def test_round_trip(self) -> None:
        p = PointRadius(lat=60.0, lon=-150.0, radius_km=150.0)
        assert PointRadius.model_validate(p.model_dump()) == p


# ── BoundingBox ───────────────────────────────────────────────────────


class TestBoundingBox:
    def test_valid(self) -> None:
        b = BoundingBox(min_lat=59.0, max_lat=61.0, min_lon=-151.0, max_lon=-149.0)
        assert b.min_lat == 59.0
        assert b.max_lat == 61.0
        assert b.type == "bbox"

    def test_inverted_lat_raises(self) -> None:
        with pytest.raises(ValidationError, match="min_lat .* must not exceed max_lat"):
            BoundingBox(min_lat=61.0, max_lat=59.0, min_lon=-151.0, max_lon=-149.0)

    def test_equal_lat_allowed(self) -> None:
        b = BoundingBox(min_lat=60.0, max_lat=60.0, min_lon=-151.0, max_lon=-149.0)
        assert b.min_lat == b.max_lat

    def test_round_trip(self) -> None:
        b = BoundingBox(min_lat=59.0, max_lat=61.0, min_lon=-151.0, max_lon=-149.0)
        assert BoundingBox.model_validate(b.model_dump()) == b
