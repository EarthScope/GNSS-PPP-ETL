"""
Local resource factory — loads local storage specs, resolves directories.

Fixes from original:
- ``resolve_directory`` uses actual model fields (not ghost ``self.metadata``)
- Factory has proper lookup methods (``get_spec``, ``collection_for_spec``, etc.)
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union

import yaml

from gnss_ppp_products.specifications.local import LocalCollection, LocalResourceSpec


class LocalResourceFactory:
    """Registry / factory for local storage layouts.

    Replaces ``_LocalResourceRegistry``.
    """

    def __init__(self) -> None:
        self._specs: Dict[str, LocalResourceSpec] = {}
        self._base_dir: Optional[Path] = None

    @property
    def base_dir(self) -> Optional[Path]:
        return self._base_dir

    @base_dir.setter
    def base_dir(self, value: Union[str, Path]) -> None:
        self._base_dir = Path(value).expanduser()

    @property
    def collections(self) -> Dict[str, LocalCollection]:
        """Merged view of all collections across loaded specs."""
        merged: Dict[str, LocalCollection] = {}
        for spec in self._specs.values():
            merged.update(spec.collections)
        return merged

    # -- loading -----------------------------------------------------

    def load_from_yaml(self, yaml_path: str | Path) -> None:
        """Load a single YAML spec file."""
        with open(yaml_path) as fh:
            raw = yaml.safe_load(fh)
        spec = LocalResourceSpec.model_validate(raw)
        self._specs[spec.name] = spec

    # -- lookup ------------------------------------------------------

    def get_spec(self, name: str = "default") -> LocalResourceSpec:
        try:
            return self._specs[name]
        except KeyError:
            raise KeyError(
                f"Local spec {name!r} not found. "
                f"Available: {list(self._specs)}"
            )

    @property
    def specs(self) -> Dict[str, LocalResourceSpec]:
        return dict(self._specs)

    def collection_for_spec(
        self, spec_name: str
    ) -> LocalCollection:
        """Find the collection containing *spec_name* across all loaded specs."""
        for local_spec in self._specs.values():
            try:
                return local_spec.collection_for_spec(spec_name)
            except KeyError:
                continue
        raise KeyError(
            f"Spec {spec_name!r} not found in any local resource spec. "
            f"Known specs: {self.all_specs}"
        )

    def collection_name_for_spec(self, spec_name: str) -> str:
        """Return the collection name that owns *spec_name*."""
        for local_spec in self._specs.values():
            try:
                return local_spec.collection_name_for_spec(spec_name)
            except KeyError:
                continue
        raise KeyError(
            f"Spec {spec_name!r} not found in any local resource spec. "
            f"Known specs: {self.all_specs}"
        )

    def resolve_directory(
        self,
        spec_name: str,
        date: Optional[datetime.date | datetime.datetime] = None,
        *,
        meta_catalog=None,
    ) -> str:
        """Resolve the directory for *spec_name* by substituting date placeholders."""
        for local_spec in self._specs.values():
            try:
                coll = local_spec.collection_for_spec(spec_name)
            except KeyError:
                continue

            if "{" not in coll.directory:
                return coll.directory

            if date is None:
                raise ValueError(
                    f"Date required to resolve directory {coll.directory!r}"
                )

            if isinstance(date, datetime.date) and not isinstance(
                date, datetime.datetime
            ):
                date = datetime.datetime(
                    date.year, date.month, date.day,
                    tzinfo=datetime.timezone.utc,
                )

            if meta_catalog is None:
                raise TypeError("meta_catalog is required to resolve date placeholders")

            return meta_catalog.resolve(coll.directory, date, computed_only=True)

        raise KeyError(
            f"Spec {spec_name!r} not found in any local resource spec. "
            f"Known specs: {self.all_specs}"
        )

    @property
    def all_specs(self) -> List[str]:
        """All product spec names across all loaded local resource specs."""
        result: List[str] = []
        for spec in self._specs.values():
            result.extend(spec.all_specs)
        return result
