"""LocalResourceFactory — collections-based local file-system product archives."""

import datetime
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from gnss_ppp_products.specifications.local.local import LocalResourceSpec
from gnss_ppp_products.specifications.parameters.parameter import ParameterCatalog
from gnss_ppp_products.specifications.products.product import Product, ProductPath
from gnss_ppp_products.specifications.remote.resource import ResourceCatalog, ResourceQuery, Server
from gnss_ppp_products.utilities.helpers import _ensure_datetime


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
        local_spec: LocalResourceSpec,
        product_catalog,
        parameter_catalog: ParameterCatalog,
        base_dir: Path,
    ) -> None:
        self._local_spec = local_spec
        self._product_catalog = product_catalog
        self._parameter_catalog = parameter_catalog
        self._base_dir = base_dir

        # Build a single local "server"
        self.local_server = Server(
            id="local_disk",
            hostname=str(base_dir) if base_dir else "local",
            protocol="file",
            auth_required=False,
            description="Local product archive",
        )

        # Build spec_name → directory_template map
        self._item_to_dir: Dict[str, str] = {}
        self._catalogs: List[ResourceCatalog] = []

        for coll_name, coll in local_spec.collections.items():
            for item in coll.items:
                self._item_to_dir[item] = coll.directory

        # Check that all specs in the product catalog have a local directory template
        for prod_name in product_catalog.products.keys():
            if prod_name not in self._item_to_dir:
                raise ValueError(
                    f"Product {prod_name!r} in catalog has no local directory template. "
                    f"Source file: {local_spec.source_file}."
                )

    def resolve_directory(
        self,
        product_name: str,
        date: datetime.date | datetime.datetime,
    ) -> Path:
        """Resolve the local directory for a product spec on a given date."""
        dt = _ensure_datetime(date)
        directory_template = self._item_to_dir.get(product_name)
        if directory_template is None:
            raise KeyError(
                f"Spec {product_name!r} not found in any local collection. "
                f"Known specs: {list(self._item_to_dir.keys())}"
            )
        resolved = self._parameter_catalog.resolve(directory_template, dt, computed_only=True)
        return self._base_dir / Path(resolved)

    def resolve_product(self, product: Product, date: datetime.datetime) -> Tuple[Server, ProductPath]:
        """Resolve a product to a (Server, ProductPath) for local access."""
        dt = _ensure_datetime(date)
        directory_template = self._item_to_dir.get(product.name)
        if directory_template is None:
            raise KeyError(
                f"Spec {product.name!r} not found in any local collection. "
                f"Known specs: {list(self._item_to_dir.keys())}"
            )
        directory_template_pp: ProductPath = ProductPath(pattern=directory_template)
        directory_template_pp.derive(product.parameters)
        return self.local_server, directory_template_pp

    def find_local_files(
        self, query: ResourceQuery, date: Optional[datetime.date] = None,
    ) -> List[Path]:
        """Search local disk for files matching a query."""
        dir_pattern = query.directory.pattern
        if date:
            dt = _ensure_datetime(date)
            dir_pattern = self._parameter_catalog.resolve(dir_pattern, dt, computed_only=True)

        if self._base_dir:
            search_dir = self._base_dir / dir_pattern
        else:
            search_dir = Path(query.server.hostname) / dir_pattern

        if not search_dir.exists():
            return []

        file_pattern = query.product.filename.pattern if query.product.filename else None
        if date and file_pattern:
            dt = _ensure_datetime(date)
            file_pattern = self._parameter_catalog.resolve(file_pattern, dt, computed_only=True)

        if file_pattern:
            return sorted(
                p for p in search_dir.iterdir()
                if p.is_file() and re.search(file_pattern, p.name, re.IGNORECASE)
            )
        return sorted(p for p in search_dir.iterdir() if p.is_file())
