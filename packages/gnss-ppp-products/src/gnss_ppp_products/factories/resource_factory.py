"""ResourceFactory — common interface for local and remote resource registries."""

from __future__ import annotations

from typing import List, Protocol, runtime_checkable

from gnss_ppp_products.specifications.products.product import Product
from gnss_ppp_products.specifications.remote.resource import ResourceQuery


@runtime_checkable
class ResourceFactory(Protocol):
    """Shared query-side interface for resource factories.

    Both ``RemoteResourceFactory`` and ``LocalResourceFactory`` satisfy
    this protocol, allowing ``QueryFactory`` and other consumers to treat
    local and remote resources uniformly.

    Registration (``register()``) is intentionally **not** part of this
    protocol — each factory accepts different spec types at setup time.
    """

    @property
    def resource_ids(self) -> List[str]:
        """Return identifiers for all registered resources."""
        ...

    def source_product(
        self, product: Product, resource_id: str, **args
    ) -> List[ResourceQuery]:
        """Resolve *product* against the resource identified by *resource_id*.

        Returns a list of ``ResourceQuery`` objects with directory and
        filename templates partially resolved from the product's parameters.
        """
        ...

    def sink_product(self, product: Product, resource_id: str, **args) -> ResourceQuery:
        """What would be the path to this product for a given resource identified by *resource_id*.

        Returns a ``ResourceQuery`` object with directory and filename templates
        partially resolved from the product's parameters.
        """
        ...

    def register(self, spec, **args) -> None:
        """Register a resource specification with the factory."""
        ...
