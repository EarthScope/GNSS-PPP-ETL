"""Pure Pydantic models for product specifications."""

from __future__ import annotations

from typing import Dict, List

import yaml
from pydantic import BaseModel, Field


class ProductFormatBinding(BaseModel):
    """A product's reference to a specific format + version + variant."""

    format: str
    version: str
    variant: str = "default"
    constraints: Dict[str, str] = Field(default_factory=dict)


class ProductSpec(BaseModel):
    """A product definition (e.g. ORBIT, CLOCK, RINEX_NAV)."""

    description: str = ""
    formats: List[ProductFormatBinding] = Field(default_factory=list)


class ProductSpecCollection(BaseModel):
    """Collection of product specifications from the ``products:`` YAML key."""

    products: Dict[str, ProductSpec] = Field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str) -> "ProductSpecCollection":
        """Load from a YAML file, extracting the ``products:`` section."""
        with open(path) as fh:
            raw = yaml.safe_load(fh)
        return cls.model_validate({"products": raw.get("products", {})})
    