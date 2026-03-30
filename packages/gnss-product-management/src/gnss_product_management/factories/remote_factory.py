"""Author: Franklyn Dunbar

RemoteResourceFactory — registry of remote data centers and their resolved catalogs.
"""

from __future__ import annotations

from datetime import datetime
import logging
import re
from typing import Dict, List, Optional

from gnss_product_management.specifications.products.product import Product, ProductPath
from gnss_product_management.specifications.remote.resource import (
    ResourceQuery,
    ResourceSpec,
    Server,
)
from gnss_product_management.specifications.remote.resource_catalog import ResourceCatalog

logger = logging.getLogger(__name__)


class RemoteResourceFactory:
    """Registry of remote data centers and their resolved catalogs.

    Attributes:
        _product_catalog: Product catalog for resolving product templates.
        _parameter_catalog: Parameter catalog for interpolation.

    Usage::

        remote = RemoteResourceFactory(product_catalog)
        remote.register(ResourceSpec(**wum_dict))
        remote.register(ResourceSpec(**igs_dict))
    """

    def __init__(
        self, product_catalog: ProductCatalog, parameter_catalog: ParameterCatalog
    ) -> None:
        """Initialise with a product and parameter catalog.

        Args:
            product_catalog: Catalog of known product types.
            parameter_catalog: Catalog of parameter definitions.
        """
        self._product_catalog = product_catalog
        self._parameter_catalog = parameter_catalog
        self._catalogs: Dict[str, ResourceCatalog] = {}
        self._specs: Dict[str, ResourceSpec] = {}

    def register(self, spec: ResourceSpec) -> ResourceCatalog:
        """Register a remote resource specification and build its catalog.

        Args:
            spec: Resource specification for a data center.

        Returns:
            The newly built :class:`ResourceCatalog`.
        """
        self._specs[spec.id] = spec
        cat = ResourceCatalog.build(
            resource_spec=spec, product_catalog=self._product_catalog
        )
        self._catalogs[cat.id] = cat
        return cat

    def register_dict(self, spec_dict: dict) -> ResourceCatalog:
        """Register a resource specification from a raw dict.

        Args:
            spec_dict: Dictionary matching :class:`ResourceSpec` schema.

        Returns:
            The newly built :class:`ResourceCatalog`.
        """
        return self.register(ResourceSpec(**spec_dict))

    def get(self, center_id: str) -> ResourceCatalog:
        """Retrieve a resource catalog by center identifier.

        Args:
            center_id: Data center identifier.

        Returns:
            The matching :class:`ResourceCatalog`.
        """
        return self._catalogs[center_id]

    @property
    def resource_ids(self) -> List[str]:
        """Identifiers for all registered resource centers."""
        return list(self._catalogs.keys())

    @property
    def centers(self) -> List[str]:
        """Alias for :attr:`resource_ids`."""
        return self.resource_ids

    @property
    def catalogs(self) -> List[ResourceCatalog]:
        """All registered resource catalogs."""
        return list(self._catalogs.values())

    @property
    def all_queries(self) -> List[ResourceQuery]:
        """Flattened list of every query across all registered centers."""
        return [q for cat in self._catalogs.values() for q in cat.queries]

    @staticmethod
    def match_pinned_query(found: Product, incoming: Product) -> Optional[Product]:
        """Check if a found query matches an incoming product based on pinned parameters.

        Args:
            found: Product from the resource catalog.
            incoming: Product being searched for.

        Returns:
            The *incoming* product with matched values filled in,
            or ``None`` if pinned parameters conflict.
        """
        found_params = {
            p.name: p.value for p in found.parameters if p.value is not None
        }
        incoming_params = {
            p.name: p.value for p in incoming.parameters if p.value is not None
        }
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

    def source_product(self, product: Product, resource_id: str) -> List[ResourceQuery]:
        """Resolve a product into all matching ResourceQueries for a remote resource.

        Args:
            product: Product to resolve.
            resource_id: Remote resource identifier.

        Returns:
            A list of :class:`ResourceQuery` objects.

        Raises:
            KeyError: If *resource_id* or *product.name* is not found.
        """
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

            matched_product: Optional[Product] = self.match_pinned_query(
                query.product, incoming
            )
            if matched_product is None:
                continue

            if query.product.filename:
                query.product.filename.derive(incoming.parameters)
            query.directory.derive(incoming.parameters)
            results.append(query)

        return results

    def sink_product(
        self, product: Product, resource_id: str, date: datetime
    ) -> ResourceQuery:
        """Resolve the remote directory/filename for uploading *product*.

        Args:
            product: Product to upload.
            resource_id: Remote resource identifier.
            date: Target date for computed fields.

        Returns:
            A :class:`ResourceQuery` with resolved paths.

        Raises:
            KeyError: If no matching entry exists.
        """
        queries = self.source_product(product, resource_id)
        if not queries:
            raise KeyError(
                f"Product {product.name!r} has no matching entry in resource {resource_id!r}."
            )
        # Use the first matching query as the canonical upload target.
        query = queries[0]
        query.product = product

        resolved_dir = self._parameter_catalog.interpolate(
            query.directory.pattern, date, computed_only=True
        )
        query.directory.value = resolved_dir
        query.product = product
        return query
