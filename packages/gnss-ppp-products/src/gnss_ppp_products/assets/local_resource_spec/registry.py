"""
Local resource registry.

Loads ``local_v2.yml`` at import time and exposes a module-level
``LocalResourceRegistry`` singleton (named ``default``) for resolving
local storage paths.

Usage::

    from gnss_ppp_products.assets.local_resource_spec import LocalResourceRegistry

    # resolve a directory for a product + date
    import datetime
    LocalResourceRegistry.resolve_directory("ORBIT", datetime.date(2025, 1, 15))
    # => "2025/015/products"

    # look up which collection a spec belongs to
    LocalResourceRegistry.collection_for_spec("ATTATX")
    # => LocalCollection(directory="table", temporal="static", ...)

    # list all known specs
    LocalResourceRegistry.all_specs
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .local_resource import LocalCollection, LocalResourceSpec

_SPEC_DIR = Path(__file__).resolve().parent


class _LocalResourceRegistry:
    """Singleton wrapping a :class:`LocalResourceSpec` loaded from YAML.

    Provides the same lookup interface as the spec object itself, plus
    a ``base_dir`` that can be set at runtime for full path resolution.
    """

    def __init__(self, spec: LocalResourceSpec) -> None:
        self._spec = spec
        self._base_dir: Optional[Path] = None
        # Build inverse index: spec_name -> collection name
        self._spec_to_collection: Dict[str, str] = {}
        for name, coll in spec.collections.items():
            for s in coll.specs:
                self._spec_to_collection[s] = name

    @classmethod
    def load_from_yaml(
        cls, path: str | Path = _SPEC_DIR / "local_v2.yml"
    ) -> "_LocalResourceRegistry":
        spec = LocalResourceSpec.from_yaml(path)
        return cls(spec)

    # ------------------------------------------------------------------
    # Base directory (set at runtime)
    # ------------------------------------------------------------------

    @property
    def base_dir(self) -> Optional[Path]:
        """Root directory for local storage, or ``None`` if not set."""
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
        """Return the collection name that owns *spec_name*."""
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
    ) -> str:
        """Resolve the relative directory for *spec_name* on *date*."""
        return self._spec.resolve_directory(spec_name, date)

    def resolve_path(
        self,
        spec_name: str,
        date: datetime.date | datetime.datetime | None = None,
    ) -> Path:
        """Resolve the full path for *spec_name* on *date*.

        Requires :attr:`base_dir` to have been set.

        Raises
        ------
        RuntimeError
            If ``base_dir`` has not been set.
        """
        if self._base_dir is None:
            raise RuntimeError(
                "base_dir has not been set on LocalResourceRegistry. "
                "Set it with: LocalResourceRegistry.base_dir = '/path/to/storage'"
            )
        rel = self.resolve_directory(spec_name, date)
        return self._base_dir / rel


# ===================================================================
# Canonical singleton — named "default"
# ===================================================================
default = _LocalResourceRegistry.load_from_yaml()
