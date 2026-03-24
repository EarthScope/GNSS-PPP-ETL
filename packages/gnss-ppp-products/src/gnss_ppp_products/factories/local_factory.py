"""LocalResourceFactory — collections-based local file-system product archives."""

from __future__ import annotations

import datetime
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from pydantic import BaseModel

from gnss_ppp_products.specifications.local.local import LocalResourceSpec
from gnss_ppp_products.specifications.parameters.parameter import ParameterCatalog
from gnss_ppp_products.specifications.products.product import Product, ProductPath
from gnss_ppp_products.specifications.remote.resource import ResourceQuery, Server
from gnss_ppp_products.specifications.remote.resource_catalog import ResourceCatalog
from gnss_ppp_products.utilities.helpers import _ensure_datetime

if TYPE_CHECKING:
    from gnss_ppp_products.specifications.products.catalog import ProductCatalog

logger = logging.getLogger(__name__)


def paths_overlap(p1: Path, p2: Path) -> bool:
    p1 = p1.resolve()
    p2 = p2.resolve()
    return p1.is_relative_to(p2) or p2.is_relative_to(p1)


class RegisteredLocalResource(BaseModel):
    name: str
    base_dir: Path
    spec: LocalResourceSpec
    item_to_dir: Dict[str, str]
    server: Server

class LocalResourceFactory:
    """Registry of local file-system product archives using collections-based layout.

    Loads a ``LocalResourceSpec`` (from ``local_config.yaml``) plus the
    ``ProductCatalog`` to produce one ``ResourceQuery`` per locally-known
    product type, using the collection's directory template and the catalog's
    filename pattern.

    Usage::

        spec = LocalResourceSpec.from_yaml("local_config.yaml")
        local = LocalResourceFactory(spec, product_catalog, parameter_catalog, base_dir=Path("/data/gnss"))
    """

    def __init__(
        self,
        product_catalog: ProductCatalog,
        parameter_catalog: ParameterCatalog,
    ) -> None:
  
        self._product_catalog = product_catalog
        self._parameter_catalog = parameter_catalog
        self._registered_specs: Dict[str,RegisteredLocalResource] = {}
        self._alias_map: Dict[str, str] = {}  # alias → spec name

        # # Build a single local "server"
        # self.local_server = Server(
        #     id="local_disk",
        #     hostname=str(base_dir) if base_dir else "local",
        #     protocol="file",
        #     auth_required=False,
        #     description="Local product archive",
        # )

        # # Build spec_name → directory_template map
        # self._item_to_dir: Dict[str, str] = {}
        # self._catalogs: List[ResourceCatalog] = []

        # for coll_name, coll in local_spec.collections.items():
        #     for item in coll.items:
        #         self._item_to_dir[item] = coll.directory

        # # Warn about products in the catalog that have no local directory template
        # for prod_name in product_catalog.products.keys():
        #     if prod_name not in self._item_to_dir:
        #         logger.warning(
        #             "Product %r in catalog has no local directory template. "
        #             "Source: %s", prod_name, local_spec.source_file,
        #         )

    def register(
        self,
        spec: LocalResourceSpec | Path | str,
        base_dir: Path | str,
        alias: Optional[str] = None,
    ) -> None:
        
        if isinstance(base_dir, str):
            base_dir = Path(base_dir)


        if isinstance(spec, (Path, str)):
            spec = LocalResourceSpec.from_yaml(str(spec))
        
        server = Server(
            id=spec.name,
            hostname=str(base_dir) if base_dir else spec.name,
            protocol="file",
            auth_required=False,
            description=spec.description,
        )


        name = spec.name
        if name in self._registered_specs:
            raise ValueError(f"Local resource {name!r} is already registered.")
        for registered_spec in self._registered_specs.values():
            # Check if any existing base directories overlap with the new spec's base directory
            if paths_overlap(registered_spec.base_dir, base_dir):
                raise ValueError(
                    f"Base directory {base_dir!r} for spec {name!r} overlaps with "
                    f"existing base directory {registered_spec.base_dir!r} for spec "
                    f"{registered_spec.name!r}. Please choose non-overlapping base "
                    f"directories for local resources."
                )
        if alias:
            if alias in self._alias_map:
                raise ValueError(f"Alias {alias!r} is already in use for spec {self._alias_map[alias]!r}.")
       

        item_to_dir: Dict[str, str] = {}
        for coll_name, coll in spec.collections.items():
            for item in coll.items:
                if item in item_to_dir:
                    raise ValueError(
                        f"Spec {item!r} is in multiple collections: "
                        f"{item_to_dir[item]!r} and {coll_name!r}"
                    )
                item_to_dir[item] = coll.directory

        self._registered_specs[name] = RegisteredLocalResource(
            name=name,
            base_dir=base_dir,
            spec=spec,
            item_to_dir=item_to_dir,
            server=server,
        )
        if alias:
            self._alias_map[alias] = name
    
    def _get_registered_spec(self, name_or_alias: str) -> RegisteredLocalResource:
        if name_or_alias in self._alias_map:
            name_or_alias = self._alias_map[name_or_alias]
        registered_spec = self._registered_specs.get(name_or_alias)
        if registered_spec is None:
            raise KeyError(
                f"Local resource {name_or_alias!r} not found. "
                f"Known resources: {list(self._registered_specs.keys())}"
            )
        return registered_spec
    
    def sink_product(
        self,
        product: Product,
        resource_id: str,
        date: datetime.date,
    ) -> ResourceQuery:
        """Resolve the local directory for a product spec on a given date."""
        dt = _ensure_datetime(date)
        registered_spec = self._get_registered_spec(resource_id)

        
        directory_template = registered_spec.item_to_dir.get(product.name)
        if directory_template is None:
            raise KeyError(
                f"Spec {product.name!r} not found in any local collection. "
                f"Known specs: {list(registered_spec.item_to_dir.keys())}"
            )
        resolved = self._parameter_catalog.resolve(directory_template, dt, computed_only=True)
        
        out_query = ResourceQuery(
            product=product,
            server=registered_spec.server,
            directory=ProductPath(pattern=directory_template, value=resolved),
        )
        return out_query

    @property
    def resource_ids(self) -> List[str]:
        """Return identifiers for all registered local resources."""
        return list(self._registered_specs.keys())

    def source_product(self, product: Product, resource_id: str) -> List[ResourceQuery]:
        """Resolve a product into ResourceQuery objects for a specific local resource.

        Looks up the registered spec identified by *resource_id* and builds
        a ``ResourceQuery`` with the collection's directory template.
        """
        registered_spec = self._get_registered_spec(resource_id)
        directory_template = registered_spec.item_to_dir.get(product.name)
        if directory_template is None:
            raise KeyError(
                f"Product {product.name!r} not found in resource {resource_id!r}. "
                f"Known products: {sorted(registered_spec.item_to_dir.keys())}"
            )
        directory = ProductPath(pattern=directory_template)
        directory.derive(product.parameters)
        return [ResourceQuery(
            product=product,
            server=registered_spec.server,
            directory=directory,
        )]

    def find_local_files(
        self, query: ResourceQuery, date: Optional[datetime.date] = None,
    ) -> List[Path]:
        """Search local disk for files matching a query."""
        dir_pattern = query.directory.pattern
        if date:
            date = _ensure_datetime(date)
            dir_pattern = self._parameter_catalog.resolve(dir_pattern, date, computed_only=True)

        # Find the registered spec that owns this query's server.
        registered_spec = None
        for candidate in self._registered_specs.values():
            if candidate.server.id == query.server.id:
                registered_spec = candidate
                break

        if registered_spec is None:
            raise KeyError(
                f"Server {query.server.id!r} not found in any registered local resource. "
                f"Known servers: {[s.server.id for s in self._registered_specs.values()]}"
            )
    

      
        file_pattern = query.product.filename.pattern if query.product.filename else None
        if date and file_pattern:
            date = _ensure_datetime(date)
            file_pattern = self._parameter_catalog.resolve(file_pattern, date, computed_only=True)
        
        search_dir = registered_spec.base_dir / Path(dir_pattern)

        if file_pattern:
            return sorted(
                p for p in search_dir.iterdir()
                if p.is_file() and re.search(file_pattern, p.name, re.IGNORECASE)
            )
        return sorted(p for p in search_dir.iterdir() if p.is_file())
