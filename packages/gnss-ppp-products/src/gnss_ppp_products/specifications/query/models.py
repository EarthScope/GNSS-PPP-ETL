"""
Pydantic models for query specifications (``query_v2.yaml``).

A :class:`QuerySpec` defines the user-facing search axes for unified
product queries.  Each :class:`ProductQueryProfile` declares which axes
apply to a given product spec and what metadata fields are fixed.

This module is agnostic — no hardcoded ``_SPEC_DIR``, no singleton.
``from_yaml`` requires an explicit path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Field


# ===================================================================
# Axis definitions
# ===================================================================


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
    """A product-specific axis that doesn't exist in the global set."""

    description: str = ""
    maps_to: List[str] = Field(default_factory=list)
    values: List[Any] = Field(default_factory=list)


# ===================================================================
# Product query profile
# ===================================================================


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


# ===================================================================
# Top-level query spec
# ===================================================================


class QuerySpec(BaseModel):
    """Top-level query specification loaded from ``query_v2.yaml``."""

    axes: Dict[str, AxisDef]
    products: Dict[str, ProductQueryProfile]

    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> "QuerySpec":
        """Load the query specification from YAML (explicit path required)."""
        with open(path) as f:
            raw = yaml.safe_load(f)

        axes = {
            name: AxisDef(**defn)
            for name, defn in raw.get("axes", {}).items()
        }

        products = {}
        for name, defn in raw.get("products", {}).items():
            extra_raw = defn.pop("extra_axes", {})
            extra = {
                k: ExtraAxisDef(**v) for k, v in extra_raw.items()
            }
            products[name] = ProductQueryProfile(extra_axes=extra, **defn)

        return cls(axes=axes, products=products)

    def axis_def(self, name: str) -> AxisDef:
        return self.axes[name]

    def profile(self, spec_name: str) -> ProductQueryProfile:
        return self.products[spec_name]

    @property
    def spec_names(self) -> List[str]:
        return list(self.products.keys())

    @property
    def solution_preference(self) -> List[str]:
        sol = self.axes.get("solution")
        if sol and sol.sort_preference:
            return sol.sort_preference
        return []
