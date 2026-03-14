"""
Pydantic models for query specifications (``query_v2.yaml``).

A :class:`QuerySpec` defines the user-facing search axes for unified
product queries.  Each :class:`ProductQueryProfile` declares which axes
apply to a given product spec and what metadata fields are fixed.

Usage::

    from gnss_ppp_products.assets.query_spec.query import QuerySpec

    qs = QuerySpec.from_yaml()
    orbit = qs.products["ORBIT"]
    print(orbit.axes)                    # ['date', 'center', 'campaign', ...]
    print(orbit.fixed)                   # {'LEN': '01D', 'CNT': 'ORB', ...}
    print(qs.axis_def("solution"))       # AxisDef(type='enum', values=[...])
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Field


_SPEC_DIR = Path(__file__).resolve().parent


# ===================================================================
# Axis definitions
# ===================================================================


class AxisDef(BaseModel):
    """A global search-axis definition."""

    description: str = ""
    type: str = "enum"                  # "enum", "computed"
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
    """Defines how a single product spec is queried.

    Attributes
    ----------
    axes : list[str]
        Ordered list of global axis names that apply to this product.
        Defines the recommended drill-down order.
    fixed : dict[str, str]
        Metadata field values baked into the product spec —
        these constrain the regex but are not user-facing axes.
    extra_axes : dict[str, ExtraAxisDef]
        Product-specific axes beyond the global set.
    format_key : str
        Which top-level format family the product uses
        (PRODUCT, RINEX, VIENNA_MAPPING_FUNCTIONS, ANTENNAE, TABLE).
    temporal : str
        'daily', 'hourly', or 'static'.
    local_collection : str
        Which LocalResourceRegistry collection stores this product.
    """

    axes: List[str] = Field(default_factory=list)
    fixed: Dict[str, str] = Field(default_factory=dict)
    extra_axes: Dict[str, ExtraAxisDef] = Field(default_factory=dict)
    format_key: str = ""
    temporal: str = "daily"
    local_collection: str = ""

    @property
    def all_axis_names(self) -> List[str]:
        """Global axes + product-specific extra axes."""
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

    # ----- factory -----

    @classmethod
    def from_yaml(
        cls,
        path: Union[str, Path] = _SPEC_DIR / "query_v2.yaml",
    ) -> "QuerySpec":
        """Load the query specification from YAML."""
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

    # ----- convenience -----

    def axis_def(self, name: str) -> AxisDef:
        """Look up a global axis definition by name."""
        return self.axes[name]

    def profile(self, spec_name: str) -> ProductQueryProfile:
        """Look up a product query profile by spec name."""
        return self.products[spec_name]

    @property
    def spec_names(self) -> List[str]:
        """All product spec names with query profiles."""
        return list(self.products.keys())

    @property
    def solution_preference(self) -> List[str]:
        """Preferred solution ordering (best quality first)."""
        sol = self.axes.get("solution")
        if sol and sol.sort_preference:
            return sol.sort_preference
        return []
