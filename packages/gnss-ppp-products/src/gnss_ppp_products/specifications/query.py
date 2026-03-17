"""Pure Pydantic models for query specifications."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AxisDef(BaseModel):
    """A global search-axis definition."""

    description: str = ""
    type: str = "enum"
    required: bool = False
    maps_to: List[str] = Field(default_factory=list)
    values: List[str] = Field(default_factory=list)
    values_from: Optional[str] = None
    sort_preference: List[str] = Field(default_factory=list)
    notes: str = ""


class ExtraAxisDef(BaseModel):
    """A product-specific axis not in the global set."""

    description: str = ""
    maps_to: List[str] = Field(default_factory=list)
    values: List[Any] = Field(default_factory=list)


class ProductQueryProfile(BaseModel):
    """Defines how a single product spec is queried."""

    axes: List[str] = Field(default_factory=list)
    extra_axes: Dict[str, ExtraAxisDef] = Field(default_factory=dict)
    format_key: str = ""
    temporal: str = "daily"
    local_collection: str = ""

    @property
    def all_axis_names(self) -> List[str]:
        return self.axes + list(self.extra_axes.keys())

    @property
    def is_static(self) -> bool:
        return self.temporal == "static"

    @property
    def is_daily(self) -> bool:
        return self.temporal == "daily"
