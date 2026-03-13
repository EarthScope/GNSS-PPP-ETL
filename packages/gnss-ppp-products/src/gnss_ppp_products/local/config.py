"""
Local Storage Configuration
============================

Loads ``local_storage.yaml`` and maps each :class:`ProductType` to the
correct :class:`BaseDirectory` method for resolving local file paths.
"""

from __future__ import annotations

import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, Optional

import yaml
from pydantic import BaseModel, model_validator

from ..assets.base import ProductType
from .base import BaseDirectory

# ---------------------------------------------------------------------------
# Path to the bundled YAML config
# ---------------------------------------------------------------------------

_YAML_PATH = Path(__file__).parent / "local_storage.yaml"


# ---------------------------------------------------------------------------
# Pydantic models that mirror the YAML schema
# ---------------------------------------------------------------------------


class TemporalCategory(str, Enum):
    """Temporal cadence declared in local_storage.yaml."""

    DAILY = "daily"
    HOURLY = "hourly"
    EPOCH = "epoch"
    STATIC = "static"


class CollectionConfig(BaseModel):
    """A single collection entry from the YAML file."""

    directory: str
    temporal: TemporalCategory
    description: str = ""
    types: list[str]


class LocalStorageSchema(BaseModel):
    """Top-level schema for ``local_storage.yaml``."""

    collections: Dict[str, CollectionConfig]


# ---------------------------------------------------------------------------
# Main config class
# ---------------------------------------------------------------------------


class LocalStorageConfig:
    """
    Maps :class:`ProductType` → local directory path using the collection
    definitions in ``local_storage.yaml`` and the directory builders in
    :class:`BaseDirectory`.

    Parameters
    ----------
    base_dir : str | Path
        Root directory for local product storage.

    Examples
    --------
    >>> cfg = LocalStorageConfig("/data/gnss")
    >>> cfg.resolve(ProductType.SP3, datetime.date(2025, 1, 15))
    PosixPath('/data/gnss/products/2025/015/common')
    >>> cfg.resolve(ProductType.ATX)
    PosixPath('/data/gnss/static/atx')
    """

    def __init__(self, base_dir: str | Path) -> None:
        self.dirs = BaseDirectory(base_dir)
        self._schema = self.load_yaml()
        self._type_to_collection = self._build_lookup()

    # -- public API ----------------------------------------------------------

    def resolve(
        self,
        product_type: ProductType,
        date: Optional[datetime.date] = None,
    ) -> Path:
        """
        Return the local directory path for *product_type* on *date*.

        Parameters
        ----------
        product_type : ProductType
            The product type to look up.
        date : datetime.date, optional
            Required for date-organised collections (daily / hourly).
            Ignored for static / epoch collections.

        Returns
        -------
        Path
            Absolute path to the target directory.

        Raises
        ------
        ValueError
            If the product type is not mapped or a date is required but missing.
        """
        name = self._collection_name(product_type)
        collection = self._schema.collections[name]
        return self._resolve_collection(collection, name, date)

    def collection_for(self, product_type: ProductType) -> str:
        """Return the collection name that owns *product_type*."""
        return self._collection_name(product_type)

    def temporal_for(self, product_type: ProductType) -> TemporalCategory:
        """Return the temporal category of *product_type*."""
        name = self._collection_name(product_type)
        return self._schema.collections[name].temporal

    @property
    def product_types(self) -> list[ProductType]:
        """All ProductType members covered by the config."""
        return list(self._type_to_collection.keys())

    # -- private helpers -----------------------------------------------------

    @staticmethod
    def load_yaml(path: str | Path = _YAML_PATH) -> LocalStorageSchema:
        with open(path) as fh:
            raw = yaml.safe_load(fh)
        return LocalStorageSchema.model_validate(raw)

    def _build_lookup(self) -> Dict[ProductType, str]:
        """Invert collections → {ProductType: collection_name}."""
        lookup: Dict[ProductType, str] = {}
        for coll_name, coll in self._schema.collections.items():
            for type_str in coll.types:
                try:
                    pt = ProductType(type_str)
                except ValueError:
                    continue
                lookup[pt] = coll_name
        return lookup

    def _collection_name(self, product_type: ProductType) -> str:
        try:
            return self._type_to_collection[product_type]
        except KeyError:
            raise ValueError(
                f"{product_type!r} is not mapped in local_storage.yaml"
            )

    def _resolve_collection(
        self,
        collection: CollectionConfig,
        name: str,
        date: Optional[datetime.datetime],
    ) -> Path:
        """Dispatch to the correct BaseDirectory method."""
        temporal = collection.temporal

        if temporal in (TemporalCategory.DAILY, TemporalCategory.HOURLY):
            if date is None:
                raise ValueError(
                    f"Collection '{name}' is {temporal.value}; a date is required"
                )
            return self._resolve_dated(name, date)

        # static / epoch  → no date needed
        return self._resolve_static(name)

    def _resolve_dated(self, name: str, date:  datetime.datetime) -> Path:
        """Map date-organised collection names to directory builders."""
        if name == "common":
            return self.dirs.products.common(date)
        if name == "navigation":
            return self.dirs.rinex.rinex(date)
        if name == "leo":
            return self.dirs.products.leo(date)
        # fallback – shouldn't happen with current YAML
        raise ValueError(f"No directory builder for dated collection '{name}'")

    def _resolve_static(self, name: str) -> Path:
        """Map static collection names to directory paths."""
        if name == "antennae":
            return self.dirs.static.atx
        if name == "reference_tables":
            return self.dirs.static.tables
        if name == "orography":
            return self.dirs.static.atmosphere
        raise ValueError(f"No directory builder for static collection '{name}'")
