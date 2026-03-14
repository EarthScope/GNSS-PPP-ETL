"""
Remote resource registry.

Auto-discovers all ``*_v2.yml`` center definitions in this directory
at import time, parses each into a :class:`RemoteResourceSpec`, and
exposes unified lookups across all centers.

The module-level ``RemoteResourceRegistry`` singleton is the single
entry point for consumers.

Usage::

    from gnss_ppp_products.assets.remote_resource_spec import RemoteResourceRegistry

    # all loaded centers
    RemoteResourceRegistry.centers              # {"WUM": ..., "IGS": ...}

    # look up by center id
    wuhan = RemoteResourceRegistry.get_center("WUM")

    # find every remote product that maps to a given ProductSpec name
    orbits = RemoteResourceRegistry.products_for_spec("ORBIT")

    # resolve a directory for a specific product + date
    import datetime
    wuhan_orbit = RemoteResourceRegistry.get_product("wuhan_orbit")
    wuhan_orbit.resolve_directory(datetime.date(2024, 1, 15))
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from .remote_resource import RemoteProduct, RemoteResourceSpec, Server

_SPEC_DIR = Path(__file__).resolve().parent


class _RemoteResourceRegistry:
    """Singleton that loads every ``*_v2.yml`` in the spec directory
    and provides cross-center lookups.
    """

    def __init__(self) -> None:
        self._centers: Dict[str, RemoteResourceSpec] = {}
        # Indexes built on load for fast lookups
        self._products_by_id: Dict[str, tuple[RemoteResourceSpec, RemoteProduct]] = {}
        self._servers_by_id: Dict[str, tuple[RemoteResourceSpec, Server]] = {}

    # ------------------------------------------------------------------
    # Loader
    # ------------------------------------------------------------------

    @classmethod
    def load_from_directory(
        cls, directory: str | Path = _SPEC_DIR
    ) -> "_RemoteResourceRegistry":
        """Discover and load all ``*_v2.yml`` files in *directory*."""
        reg = cls()
        for yml in sorted(Path(directory).glob("*_v2.yml")):
            spec = RemoteResourceSpec.from_yaml(yml)
            reg._register(spec)
        return reg

    def _register(self, spec: RemoteResourceSpec) -> None:
        self._centers[spec.id] = spec
        for srv in spec.servers:
            self._servers_by_id[srv.id] = (spec, srv)
        for prod in spec.products:
            self._products_by_id[prod.id] = (spec, prod)

    # ------------------------------------------------------------------
    # center-level look-ups
    # ------------------------------------------------------------------

    @property
    def centers(self) -> Dict[str, RemoteResourceSpec]:
        """All loaded centers, keyed by id (e.g. ``"WUM"``, ``"IGS"``)."""
        return dict(self._centers)

    def get_center(self, center_id: str) -> RemoteResourceSpec:
        """Return a :class:`RemoteResourceSpec` by center id."""
        try:
            return self._centers[center_id]
        except KeyError:
            raise KeyError(
                f"center {center_id!r} not found. "
                f"Available: {list(self._centers)}"
            )

    # ------------------------------------------------------------------
    # Product-level look-ups (across all centers)
    # ------------------------------------------------------------------

    def get_product(self, product_id: str) -> RemoteProduct:
        """Return a :class:`RemoteProduct` by its unique id."""
        try:
            return self._products_by_id[product_id][1]
        except KeyError:
            raise KeyError(
                f"Product {product_id!r} not found in any center. "
                f"Available: {list(self._products_by_id)}"
            )

    def get_product_center(self, product_id: str) -> RemoteResourceSpec:
        """Return the center that owns *product_id*."""
        try:
            return self._products_by_id[product_id][0]
        except KeyError:
            raise KeyError(f"Product {product_id!r} not found in any center.")

    def products_for_spec(self, spec_name: str) -> List[RemoteProduct]:
        """Return every :class:`RemoteProduct` referencing a ProductSpec name,
        across all centers."""
        return [
            prod
            for _, prod in self._products_by_id.values()
            if prod.spec_name == spec_name
        ]

    @property
    def all_products(self) -> List[RemoteProduct]:
        """Flat list of every product from every center."""
        return [prod for _, prod in self._products_by_id.values()]

    # ------------------------------------------------------------------
    # Server-level look-ups
    # ------------------------------------------------------------------

    def get_server(self, server_id: str) -> Server:
        """Return a :class:`Server` by its unique id."""
        try:
            return self._servers_by_id[server_id][1]
        except KeyError:
            raise KeyError(
                f"Server {server_id!r} not found. "
                f"Available: {list(self._servers_by_id)}"
            )

    def get_server_for_product(self, product_id: str) -> Server:
        """Return the :class:`Server` hosting *product_id*."""
        prod = self.get_product(product_id)
        center = self.get_product_center(product_id)
        return center.get_server(prod.server_id)


# ===================================================================
# Canonical singleton — import this everywhere
# ===================================================================
RemoteResourceRegistry = _RemoteResourceRegistry.load_from_directory()
