"""
Pydantic models for local storage specifications (``local_v2.yml``).

A :class:`LocalResourceSpec` defines how downloaded GNSS products are
organized on disk.  Each :class:`LocalCollection` groups product spec
names that share the same directory template and temporal category.

This module is agnostic — it does not import any global singletons.
Callers pass a metadata registry instance explicitly when calling
``resolve_directory``.
"""

from __future__ import annotations

import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Union

import yaml
from pydantic import BaseModel, Field


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
        meta_registry=None,
    ) -> str:
        """Resolve directory template placeholders using *date*.

        Parameters
        ----------
        meta_registry
            Metadata registry instance.  **Required** for non-static
            collections — this module does not fall back to a global
            singleton.

        Raises
        ------
        ValueError
            If a date is required but not provided.
        TypeError
            If *meta_registry* is ``None`` for a non-static collection.
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

        if meta_registry is None:
            raise TypeError(
                "meta_registry is required — specifications.local.models "
                "does not use global singletons"
            )

        return meta_registry.resolve(
            self.directory, date, computed_only=True
        )


# ===================================================================
# Root model
# ===================================================================


class LocalResourceSpec(BaseModel):
    """Root model for ``local_v2.yml``."""

    collections: Dict[str, LocalCollection] = Field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> "LocalResourceSpec":
        with open(path) as fh:
            raw = yaml.safe_load(fh)
        return cls.model_validate(raw)

    def get_collection(self, name: str) -> LocalCollection:
        try:
            return self.collections[name]
        except KeyError:
            raise KeyError(
                f"Collection {name!r} not found. "
                f"Available: {list(self.collections)}"
            )

    def collection_for_spec(self, spec_name: str) -> LocalCollection:
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
        meta_registry=None,
    ) -> str:
        return self.collection_for_spec(spec_name).resolve_directory(
            date, meta_registry=meta_registry
        )

    @property
    def all_specs(self) -> List[str]:
        return [s for coll in self.collections.values() for s in coll.specs]
