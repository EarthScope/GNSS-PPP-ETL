"""Pure Pydantic models for product specifications."""

from __future__ import annotations

from typing import Dict, List

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
