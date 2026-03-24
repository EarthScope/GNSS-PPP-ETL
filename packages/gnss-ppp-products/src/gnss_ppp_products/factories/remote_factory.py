"""RemoteResourceFactory — registry of remote data centers and their resolved catalogs."""

import logging
from typing import Dict, List, Optional

from gnss_ppp_products.specifications.products.product import Product, ProductPath
from gnss_ppp_products.specifications.remote.resource import (
    ResourceQuery,
    ResourceSpec,
    Server,
)
from gnss_ppp_products.specifications.remote.resource_catalog import ResourceCatalog

logger = logging.getLogger(__name__)


class RemoteResourceFactory:
    """Registry of remote data centers and their resolved catalogs.

    Usage::

        remote = RemoteResourceFactory(product_catalog)
        remote.register(ResourceSpec(**wum_dict))
        remote.register(ResourceSpec(**igs_dict))
    """

    def __init__(self, product_catalog) -> None:
        self._product_catalog = product_catalog
        self._catalogs: Dict[str, ResourceCatalog] = {}
        self._specs: Dict[str, ResourceSpec] = {}

    def register(self, spec: ResourceSpec) -> ResourceCatalog:
        self._specs[spec.id] = spec
        cat = ResourceCatalog.resolve(resource_spec=spec, product_catalog=self._product_catalog)
        self._catalogs[cat.id] = cat
        return cat

    def register_dict(self, spec_dict: dict) -> ResourceCatalog:
        return self.register(ResourceSpec(**spec_dict))

    def get(self, center_id: str) -> ResourceCatalog:
        return self._catalogs[center_id]

    @property
    def centers(self) -> List[str]:
        return list(self._catalogs.keys())

    @property
    def catalogs(self) -> List[ResourceCatalog]:
        return list(self._catalogs.values())

    @property
    def all_queries(self) -> List[ResourceQuery]:
        return [q for cat in self._catalogs.values() for q in cat.queries]

    @staticmethod
    def match_pinned_query(found: Product, incoming: Product) -> Optional[Product]:
        """Check if a found query matches an incoming product based on pinned parameters."""
        found_params = {p.name: p.value for p in found.parameters if p.value is not None}
        incoming_params = {p.name: p.value for p in incoming.parameters if p.value is not None}
        matching_keys = set(found_params.keys()) & set(incoming_params.keys())
        for key in matching_keys:
            found_val = found_params[key]
            incoming_val = incoming_params[key]
            if found_val != incoming_val:
                return None

        for p in incoming.parameters:
            if p.value is None and p.name in found_params:
                p.value = found_params.get(p.name)
        return incoming

    def resolve_product(self, product: Product, resource_id: str) -> List[ResourceQuery]:
        """Resolve a product into all matching ResourceQuerys for a specific remote resource."""
        cat = self._catalogs.get(resource_id)
        if cat is None:
            raise KeyError(
                f"Resource {resource_id!r} not found in remote catalogs. "
                f"Known resources: {list(self._catalogs.keys())}"
            )
        candidates = [q for q in cat.queries if q.product.name == product.name]
        if not candidates:
            raise KeyError(
                f"Product {product.name!r} not found in resource {resource_id!r}. "
                f"Known products: {set(q.product.name for q in cat.queries)}"
            )

        results: List[ResourceQuery] = []
        for query in candidates:
            # Deep copy so we never mutate the catalog's original query
            query = query.model_copy(deep=True)
            incoming = product.model_copy(deep=True)

            matched_product: Optional[Product] = self.match_pinned_query(query.product, incoming)
            if matched_product is None:
                continue

            if query.product.filename:
                query.product.filename.derive(incoming.parameters)
            query.directory.derive(incoming.parameters)
            results.append(query)

        return results
