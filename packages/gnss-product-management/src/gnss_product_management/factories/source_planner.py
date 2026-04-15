"""SourcePlanner — common interface for local and remote search planners."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from gnss_product_management.specifications.products.product import Product
from gnss_product_management.specifications.remote.resource import SearchTarget


@runtime_checkable
class SourcePlanner(Protocol):
    """Shared query-side interface for search planners.

    Both ``RemoteSearchPlanner`` and ``LocalSearchPlanner`` satisfy
    this protocol, allowing ``SearchPlanner`` and other consumers to treat
    local and remote resources uniformly.

    Registration (``register()``) is intentionally **not** part of this
    protocol — each planner accepts different spec types at setup time.
    """

    @property
    def resource_ids(self) -> list[str]:
        """Return identifiers for all registered resources."""
        ...

    def source_product(self, product: Product, resource_id: str, **args) -> list[SearchTarget]:
        """Resolve *product* against the resource identified by *resource_id*.

        Args:
            product: Product to resolve.
            resource_id: Identifier of the target resource.
            **args: Additional keyword arguments.

        Returns:
            A list of :class:`SearchTarget` objects.
        """
        ...

    def sink_product(self, product: Product, resource_id: str, **args) -> SearchTarget:
        """Return the target path for *product* on *resource_id*.

        Args:
            product: Product to resolve.
            resource_id: Identifier of the target resource.
            **args: Additional keyword arguments.

        Returns:
            A :class:`SearchTarget` with resolved path templates.
        """
        ...

    def register(self, spec, **args) -> None:
        """Register a resource specification with the planner.

        Args:
            spec: The resource specification to register.
            **args: Additional keyword arguments.
        """
        ...
