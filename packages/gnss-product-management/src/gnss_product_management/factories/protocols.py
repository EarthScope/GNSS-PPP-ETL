"""Structural protocols for the SearchPlanner query pipeline."""

from __future__ import annotations

import datetime
from typing import Protocol, runtime_checkable

from gnss_product_management.specifications.products.product import Product
from gnss_product_management.specifications.remote.resource import SearchTarget


@runtime_checkable
class QueryPlanner(Protocol):
    """Duck-typed interface consumed by :meth:`SearchPlanner.build_queries_from_planner`.

    Any object that exposes ``resource_ids``, ``source_product``, and
    ``_parameter_catalog`` (with an ``interpolate`` method) can be passed
    as a *query_planner*.

    Satisfied by :class:`ProductRegistry`, :class:`WorkSpace`, and
    :class:`GNSSNetworkRegistry` (after ``bind()``).
    """

    @property
    def resource_ids(self) -> list[str]: ...

    def source_product(self, product: Product, resource_id: str) -> list[SearchTarget]: ...

    class _ParameterCatalogLike(Protocol):
        def interpolate(
            self,
            template: str,
            date: datetime.datetime,
            *,
            computed_only: bool = False,
        ) -> str: ...

    @property
    def _parameter_catalog(self) -> _ParameterCatalogLike | None: ...
