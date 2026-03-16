"""
Pydantic models for local storage specifications (``local_v2.yml``).

A :class:`LocalResourceSpec` defines how downloaded GNSS products are
organized on disk.  Each :class:`LocalCollection` groups product spec
names that share the same directory template and temporal category.

Usage::

    from gnss_ppp_products.assets.local_resource_spec.local_resource import (
        LocalResourceSpec,
    )

    spec = LocalResourceSpec.from_yaml("local_v2.yml")

    # resolve a directory for a product + date
    import datetime
    path = spec.resolve_directory("ORBIT", datetime.date(2025, 1, 15))
    # => "2025/015/products"
"""

from __future__ import annotations

import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Field

from gnss_ppp_products.assets.meta_spec import MetaDataRegistry


# ===================================================================
# Temporal category
# ===================================================================


class TemporalCategory(str, Enum):
    DAILY = "daily"
    HOURLY = "hourly"
    STATIC = "static"


# ===================================================================
# Collection
# ===================================================================


class LocalCollection(BaseModel):
    """A group of product specs sharing a directory and temporal category."""

    directory: str
    temporal: TemporalCategory
    description: str = ""
    specs: List[str] = Field(default_factory=list)

    def resolve_directory(
        self,
        date: datetime.date | datetime.datetime | None = None,
        *,
        meta_registry: "_MetadataRegistry | None" = None,
    ) -> str:
        """Resolve directory template placeholders using *date*.

        Static collections ignore *date* and return the template as-is.
        Daily/hourly collections require a date and substitute computed
        metadata fields (``{YYYY}``, ``{DDD}``, etc.).

        Parameters
        ----------
        meta_registry
            Optional metadata registry instance.  Falls back to the
            global :data:`MetaDataRegistry` singleton when ``None``.

        Raises
        ------
        ValueError
            If a date is required but not provided.
        """
        if self.temporal == TemporalCategory.STATIC:
            return self.directory

        if date is None:
            raise ValueError(
                f"Collection with temporal={self.temporal.value!r} "
                f"requires a date to resolve directory {self.directory!r}"
            )

        if isinstance(date, datetime.date) and not isinstance(date, datetime.datetime):
            date = datetime.datetime(
                date.year, date.month, date.day,
                tzinfo=datetime.timezone.utc,
            )

        reg = meta_registry if meta_registry is not None else MetaDataRegistry
        return reg.resolve(
            self.directory, date, computed_only=True
        )


# ===================================================================
# Root model
# ===================================================================


class LocalResourceSpec(BaseModel):
    """Root model for ``local_v2.yml``.

    Attributes
    ----------
    collections : dict[str, LocalCollection]
        Named groups of product specs mapped to directory templates.
    """

    collections: Dict[str, LocalCollection] = Field(default_factory=dict)

    # ------------------------------------------------------------------
    # Loader
    # ------------------------------------------------------------------

    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> "LocalResourceSpec":
        """Load a ``LocalResourceSpec`` from a YAML file."""
        with open(path) as fh:
            raw = yaml.safe_load(fh)
        return cls.model_validate(raw)

    # ------------------------------------------------------------------
    # Look-ups
    # ------------------------------------------------------------------

    def get_collection(self, name: str) -> LocalCollection:
        """Return a :class:`LocalCollection` by name."""
        try:
            return self.collections[name]
        except KeyError:
            raise KeyError(
                f"Collection {name!r} not found. "
                f"Available: {list(self.collections)}"
            )

    def collection_for_spec(self, spec_name: str) -> LocalCollection:
        """Return the collection that contains *spec_name*."""
        for coll in self.collections.values():
            if spec_name in coll.specs:
                return coll
        raise KeyError(
            f"Spec {spec_name!r} not found in any collection. "
            f"Known specs: {self.all_specs}"
        )

    def resolve_directory(
        self,
        spec_name: str,
        date: datetime.date | datetime.datetime | None = None,
        *,
        meta_registry: "_MetadataRegistry | None" = None,
    ) -> str:
        """Resolve the local directory for *spec_name* on *date*."""
        return self.collection_for_spec(spec_name).resolve_directory(
            date, meta_registry=meta_registry
        )

    @property
    def all_specs(self) -> List[str]:
        """Flat list of every spec name across all collections."""
        return [s for coll in self.collections.values() for s in coll.specs]
