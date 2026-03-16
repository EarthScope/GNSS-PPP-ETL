"""
Local resource registry — pure spec code.

No singleton created at import; no default YAML path hardcoded.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .models import LocalCollection, LocalResourceSpec


class _LocalResourceRegistry:
    """Registry wrapping a :class:`LocalResourceSpec` loaded from YAML."""

    def __init__(self, spec: LocalResourceSpec) -> None:
        self._spec = spec
        self._base_dir: Optional[Path] = None
        self._spec_to_collection: Dict[str, str] = {}
        for name, coll in spec.collections.items():
            for s in coll.specs:
                self._spec_to_collection[s] = name

    @classmethod
    def load_from_yaml(cls, path: str | Path) -> "_LocalResourceRegistry":
        """Load from an explicit YAML path (no default)."""
        spec = LocalResourceSpec.from_yaml(path)
        return cls(spec)

    # ------------------------------------------------------------------
    # Base directory
    # ------------------------------------------------------------------

    @property
    def base_dir(self) -> Optional[Path]:
        return self._base_dir

    @base_dir.setter
    def base_dir(self, value: str | Path) -> None:
        self._base_dir = Path(value)

    # ------------------------------------------------------------------
    # Collection look-ups
    # ------------------------------------------------------------------

    @property
    def collections(self) -> Dict[str, LocalCollection]:
        return dict(self._spec.collections)

    def get_collection(self, name: str) -> LocalCollection:
        return self._spec.get_collection(name)

    def collection_for_spec(self, spec_name: str) -> LocalCollection:
        return self._spec.collection_for_spec(spec_name)

    # ------------------------------------------------------------------
    # Spec look-ups
    # ------------------------------------------------------------------

    @property
    def all_specs(self) -> List[str]:
        return self._spec.all_specs

    def collection_name_for_spec(self, spec_name: str) -> str:
        try:
            return self._spec_to_collection[spec_name]
        except KeyError:
            raise KeyError(
                f"Spec {spec_name!r} not found. "
                f"Available: {list(self._spec_to_collection)}"
            )

    # ------------------------------------------------------------------
    # Directory resolution
    # ------------------------------------------------------------------

    def resolve_directory(
        self,
        spec_name: str,
        date: datetime.date | datetime.datetime | None = None,
        *,
        meta_registry=None,
    ) -> str:
        return self._spec.resolve_directory(
            spec_name, date, meta_registry=meta_registry
        )

    def resolve_path(
        self,
        spec_name: str,
        date: datetime.date | datetime.datetime | None = None,
        *,
        meta_registry=None,
    ) -> Path:
        if self._base_dir is None:
            raise RuntimeError(
                "base_dir has not been set on _LocalResourceRegistry."
            )
        rel = self.resolve_directory(spec_name, date, meta_registry=meta_registry)
        return self._base_dir / rel
