"""Pure Pydantic models and result types for dependency specifications."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# Path is kept for DependencySpec.from_yaml signature compatibility
import yaml
from pydantic import BaseModel, Field, model_validator


class SearchPreference(BaseModel):
    """One slot in the preference cascade."""

    parameter: str
    sorting: list[str] = Field(
        default_factory=list,
        description="List of product parameters to sort by for this preference.",
    )
    description: str = ""


class Dependency(BaseModel):
    """A single product dependency."""

    spec: str
    required: bool = True
    description: str = ""
    constraints: dict[str, str] = Field(default_factory=dict)

    # RINEX_OBS-specific fields
    stations: list[str] | None = Field(
        default=None,
        description="Explicit station codes for RINEX_OBS deps (requires .centers to be set).",
    )
    station_spatial: dict | None = Field(
        default=None,
        description=(
            "GeoJSON Point geometry with required 'radius_km' for spatial RINEX_OBS queries."
        ),
    )
    rinex_version: str = Field(
        default="3",
        description="RINEX version: '2' or '3'.  Only used for RINEX_OBS deps.",
    )

    @model_validator(mode="after")
    def _validate_rinex_obs_fields(self) -> Dependency:
        """Enforce RINEX_OBS field constraints."""
        has_stations = self.stations is not None
        has_spatial = self.station_spatial is not None

        if (has_stations or has_spatial) and self.spec != "RINEX_OBS":
            raise ValueError(
                f"'stations' and 'station_spatial' are only valid when spec='RINEX_OBS'; "
                f"got spec={self.spec!r}."
            )

        if has_stations and has_spatial:
            raise ValueError(
                "RINEX_OBS dependency cannot have both 'stations' and 'station_spatial' "
                "set at the same time.  Use exactly one."
            )

        return self

    def build_spatial_filter(self):
        """Build a :class:`PointRadius` from the GeoJSON ``station_spatial`` dict.

        Only ``type: "Point"`` geometries are supported; ``BoundingBox`` is
        not expressible in the YAML format.

        Returns:
            A :class:`PointRadius` instance.

        Raises:
            ValueError: If ``station_spatial`` is ``None`` or has an
                unsupported GeoJSON type.
        """
        if self.station_spatial is None:
            raise ValueError("station_spatial is not set.")
        from gnss_product_management.environments.gnss_station_network import PointRadius

        geo = self.station_spatial
        geo_type = geo.get("type", "")
        if geo_type == "Point":
            coords = geo.get("coordinates", [])
            if len(coords) < 2:
                raise ValueError("GeoJSON Point must have [lon, lat] coordinates.")
            lon, lat = float(coords[0]), float(coords[1])
            radius_km = float(geo.get("radius_km", 0.0))
            return PointRadius(lat=lat, lon=lon, radius_km=radius_km)
        raise ValueError(
            f"Unsupported GeoJSON type for station_spatial: {geo_type!r}. "
            "Only 'Point' is supported."
        )


class DependencySpec(BaseModel):
    """Full dependency specification for a processing task."""

    name: str
    description: str = ""
    preferences: list[SearchPreference] = Field(default_factory=list)
    dependencies: list[Dependency] = Field(default_factory=list)
    package: str
    task: str

    @classmethod
    def from_yaml(cls, path: str | Path) -> DependencySpec:
        """Load a dependency specification from a YAML file.

        Args:
            path: Path to the YAML file.

        Returns:
            A :class:`DependencySpec` instance.
        """
        with open(path) as fh:
            raw = yaml.safe_load(fh)
        return cls.model_validate(raw)


class ResolvedDependency(BaseModel):
    """Resolution result for one dependency."""

    spec: str
    required: bool
    status: str  # "local" | "downloaded" | "remote" | "missing"

    # Stored as a URI string so it works for both local paths and cloud
    # URIs (e.g. ``s3://bucket/path/file.sp3``).  Use
    # ``gnss_product_management.utilities.paths.as_path(local_path)``
    # to obtain a path object for filesystem operations.
    local_path: str | None = None

    # Lockfile fields — populated during resolution for later export
    remote_url: str | None = None


@dataclass
class DependencyResolution:
    """Aggregated resolution result for all dependencies in a spec.

    Attributes:
        spec_name: Name of the dependency specification.
        resolved: List of :class:`ResolvedDependency` results.
    """

    spec_name: str
    resolved: list[ResolvedDependency] = field(default_factory=list)

    @property
    def fulfilled(self) -> list[ResolvedDependency]:
        """Dependencies that have been resolved (not missing)."""
        return [r for r in self.resolved if r.status != "missing"]

    @property
    def missing(self) -> list[ResolvedDependency]:
        """Dependencies that could not be resolved."""
        return [r for r in self.resolved if r.status == "missing"]

    @property
    def all_required_fulfilled(self) -> bool:
        """``True`` if every required dependency has been resolved."""
        return all(r.status != "missing" for r in self.resolved if r.required)

    def product_paths(self) -> dict[str, str]:
        """Return a ``{spec: uri}`` mapping for resolved local files.

        Values are URI strings that work for both local paths and cloud
        locations.  Pass them through
        ``gnss_product_management.utilities.paths.as_path()`` to get a
        path object suitable for filesystem operations.

        Returns:
            Dict mapping spec names to their local-path or cloud URIs.
        """
        return {r.spec: r.local_path for r in self.resolved if r.local_path is not None}

    def summary(self) -> str:
        """Return a one-line summary of resolution counts.

        Returns:
            Human-readable summary string.
        """
        total = len(self.resolved)
        local = sum(1 for r in self.resolved if r.status == "local")
        downloaded = sum(1 for r in self.resolved if r.status == "downloaded")
        missing_count = sum(1 for r in self.resolved if r.status == "missing")
        return (
            f"DependencyResolution({self.spec_name}): "
            f"{total} deps — "
            f"{local} local, {downloaded} downloaded, "
            f"{missing_count} missing"
        )

    def table(self) -> str:
        """Return a formatted table of all resolved dependencies.

        Returns:
            Multi-line string with columns for spec, required,
            status, and path.
        """
        lines = [f"{'spec':<14s} {'required':<10s} {'status':<12s} {'preference':<20s} {'path'}"]
        lines.append("-" * 90)
        for r in self.resolved:
            path_str = str(r.local_path) if r.local_path else "(none)"
            lines.append(
                f"{r.spec:<14s} {'yes' if r.required else 'no':<10s} {r.status:<12s} {path_str}"
            )
        return "\n".join(lines)
