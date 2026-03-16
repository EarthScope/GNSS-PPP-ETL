"""
Remote resource registry — pure spec code.

No singleton created at import; no default directory hardcoded.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from .models import RemoteProduct, RemoteResourceSpec, Server


class _RemoteResourceRegistry:
    """Registry of remote data centers."""

    def __init__(self) -> None:
        self._centers: Dict[str, RemoteResourceSpec] = {}
        self._products_by_id: Dict[str, tuple[RemoteResourceSpec, RemoteProduct]] = {}
        self._servers_by_id: Dict[str, tuple[RemoteResourceSpec, Server]] = {}

    # ------------------------------------------------------------------
    # Loader
    # ------------------------------------------------------------------

  
    def load_from_yaml(self, yaml_path: str | Path) -> None:
        """Load a single YAML spec file."""
        spec = RemoteResourceSpec.from_yaml(yaml_path)
        self._register(spec)

    def _register(self, spec: RemoteResourceSpec) -> None:
        self._centers[spec.id] = spec
        for srv in spec.servers:
            self._servers_by_id[srv.id] = (spec, srv)
        for prod in spec.products:
            self._products_by_id[prod.id] = (spec, prod)

    # ------------------------------------------------------------------
    # Center-level look-ups
    # ------------------------------------------------------------------

    @property
    def centers(self) -> Dict[str, RemoteResourceSpec]:
        return dict(self._centers)

    def get_center(self, center_id: str) -> RemoteResourceSpec:
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
        try:
            return self._products_by_id[product_id][1]
        except KeyError:
            raise KeyError(
                f"Product {product_id!r} not found in any center. "
                f"Available: {list(self._products_by_id)}"
            )

    def get_product_center(self, product_id: str) -> RemoteResourceSpec:
        try:
            return self._products_by_id[product_id][0]
        except KeyError:
            raise KeyError(f"Product {product_id!r} not found in any center.")

    def products_for_spec(self, spec_name: str) -> List[RemoteProduct]:
        return [
            prod
            for _, prod in self._products_by_id.values()
            if prod.spec_name == spec_name
        ]

    @property
    def all_products(self) -> List[RemoteProduct]:
        return [prod for _, prod in self._products_by_id.values()]

    # ------------------------------------------------------------------
    # Server-level look-ups
    # ------------------------------------------------------------------

    def get_server(self, server_id: str) -> Server:
        try:
            return self._servers_by_id[server_id][1]
        except KeyError:
            raise KeyError(
                f"Server {server_id!r} not found. "
                f"Available: {list(self._servers_by_id)}"
            )

    def get_server_for_product(self, product_id: str) -> Server:
        prod = self.get_product(product_id)
        center = self.get_product_center(product_id)
        return center.get_server(prod.server_id)
