"""
Remote resource factory — loads center specs, indexes products and servers.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from gnss_ppp_products.specifications.remote.remote import (
    RemoteProductSpec,
    RemoteResourceSpec,
    ServerSpec,
)


class RemoteResourceFactory:
    """Registry of remote data centers and their products.

    Replaces ``_RemoteResourceRegistry``.
    """

    def __init__(self) -> None:
        self._centers: Dict[str, RemoteResourceSpec] = {}
        self._products_by_id: Dict[str, tuple[RemoteResourceSpec, RemoteProductSpec]] = {}
        self._servers_by_id: Dict[str, tuple[RemoteResourceSpec, ServerSpec]] = {}

    # -- loading -----------------------------------------------------

    def load_from_yaml(self, yaml_path: str | Path) -> None:
        with open(yaml_path) as fh:
            raw = yaml.safe_load(fh)
        spec = RemoteResourceSpec.model_validate(raw)
        self._register(spec)

    @classmethod
    def load_from_directory(cls, directory: str | Path) -> "RemoteResourceFactory":
        """Load all YAML files in *directory* and return a populated factory."""
        factory = cls()
        d = Path(directory)
        for p in sorted(d.glob("*.yaml")) + sorted(d.glob("*.yml")):
            factory.load_from_yaml(p)
        return factory

    def _register(self, spec: RemoteResourceSpec) -> None:
        self._centers[spec.id] = spec
        for srv in spec.servers:
            self._servers_by_id[srv.id] = (spec, srv)
        for prod in spec.products:
            self._products_by_id[prod.id] = (spec, prod)

    # -- center look-ups ---------------------------------------------

    @property
    def centers(self) -> Dict[str, RemoteResourceSpec]:
        return dict(self._centers)

    def get_center(self, center_id: str) -> RemoteResourceSpec:
        try:
            return self._centers[center_id]
        except KeyError:
            raise KeyError(
                f"Center {center_id!r} not found. "
                f"Available: {list(self._centers)}"
            )

    # -- product look-ups --------------------------------------------

    def get_product(self, product_id: str) -> RemoteProductSpec:
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

    def products_for_spec(self, spec_name: str) -> List[RemoteProductSpec]:
        return [
            prod
            for _, prod in self._products_by_id.values()
            if prod.spec_name == spec_name
        ]

    @property
    def all_products(self) -> List[RemoteProductSpec]:
        return [prod for _, prod in self._products_by_id.values()]

    # -- server look-ups ---------------------------------------------

    def get_server(self, server_id: str) -> ServerSpec:
        try:
            return self._servers_by_id[server_id][1]
        except KeyError:
            raise KeyError(
                f"Server {server_id!r} not found. "
                f"Available: {list(self._servers_by_id)}"
            )

    def get_server_for_product(self, product_id: str) -> ServerSpec:
        prod = self.get_product(product_id)
        center = self.get_product_center(product_id)
        return center.get_server(prod.server_id)

    # -- directory resolution ----------------------------------------

    def resolve_product_directory(
        self,
        product_id: str,
        date: datetime.date | datetime.datetime,
        *,
        meta_catalog=None,
    ) -> str:
        """Resolve the directory template for a remote product."""
        prod = self.get_product(product_id)
        if isinstance(date, datetime.date) and not isinstance(date, datetime.datetime):
            date = datetime.datetime(
                date.year, date.month, date.day,
                tzinfo=datetime.timezone.utc,
            )
        if meta_catalog is None:
            raise TypeError("meta_catalog is required")
        return meta_catalog.resolve(prod.directory, date, computed_only=True)
