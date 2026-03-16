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
from typing import Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Field, model_validator


# ===================================================================
# Collection
# ===================================================================


class LocalCollection(BaseModel):
    """A group of product specs sharing a directory and temporal category."""

    directory: str
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
        if self.metadata is None:
            # No need to resolve 
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
    name:str 
    _base_dir: Optional[Path] = Field(default=None, repr=False)
    collections: Dict[str, LocalCollection] = Field(default_factory=dict)
    _spec_to_collection_map: Dict[str, str] = Field(default_factory=dict, repr=False)

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

        # Check that the spec exists and get its collection
        try:
            collection_name: str = self._spec_to_collection_map[spec_name]
        except KeyError:
            raise KeyError(
                f"Spec {spec_name!r} not found in any collection. "
                f"Known specs: {self.all_specs}"
            )
    
        return self.get_collection(collection_name).resolve_directory(
            date, meta_registry=meta_registry
        )

    @property
    def all_specs(self) -> List[str]:
        return [s for coll in self.collections.values() for s in coll.specs]

    # Validation to ensure that each spec is in exactly one collection
    @model_validator(mode="after")
    def _validate_spec_uniqueness(self) -> None:
        spec_to_collection: Dict[str, str] = {}
        for coll_name, coll in self.collections.items():
            for s in coll.specs:
                if s in spec_to_collection:
                    raise ValueError(
                        f"Spec {s!r} is in multiple collections: "
                        f"{spec_to_collection[s]!r} and {coll_name!r}"
                    )
                spec_to_collection[s] = coll_name
        self._spec_to_collection_map = spec_to_collection

    @property
    def base_dir(self) -> Optional[Path]:
        return self._base_dir
    
    @base_dir.setter
    def base_dir(self, value: str | Path) -> None:
        self._base_dir = Path(value)