"""Author: Franklyn Dunbar

ResourceFactory — common interface for local and remote resource registries.
"""

from __future__ import annotations

from typing import List, Protocol, runtime_checkable

from gnss_product_management.specifications.products.product import Product
from gnss_product_management.specifications.remote.resource import ResourceQuery


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

        Args:
            product: Product to resolve.
            resource_id: Identifier of the target resource.
            **args: Additional keyword arguments.

        Returns:
            A list of :class:`ResourceQuery` objects.
        """
        ...

    def sink_product(self, product: Product, resource_id: str, **args) -> ResourceQuery:
        """Return the target path for *product* on *resource_id*.

        Args:
            product: Product to resolve.
            resource_id: Identifier of the target resource.
            **args: Additional keyword arguments.

        Returns:
            A :class:`ResourceQuery` with resolved path templates.
        """
        ...

    def register(self, spec, **args) -> None:
        """Register a resource specification with the factory.

        Args:
            spec: The resource specification to register.
            **args: Additional keyword arguments.
        """
        ...
