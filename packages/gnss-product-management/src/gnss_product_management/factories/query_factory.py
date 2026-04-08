"""Author: Franklyn Dunbar

QueryFactory — backward-compatible alias for SearchPlanner.

.. deprecated::
    Import :class:`SearchPlanner` from
    ``gnss_product_management.factories.search_planner`` instead.
"""

from gnss_product_management.factories.search_planner import SearchPlanner
from gnss_product_management.environments import ProductRegistry
from gnss_product_management.environments import WorkSpace


class QueryFactory(SearchPlanner):
    """Backward-compatible subclass of :class:`SearchPlanner`.

    Accepts the old ``product_environment`` keyword argument in addition
    to the new ``product_registry`` keyword argument.
    """

    def __init__(
        self,
        product_registry: ProductRegistry = None,
        workspace: WorkSpace = None,
        # old keyword kept for backward compat
        product_environment: ProductRegistry = None,
    ):
        """Initialise the query factory.

        Args:
            product_registry: Built :class:`ProductRegistry` with
                catalogs and remote planner ready.
            workspace: :class:`WorkSpace` with registered local resources.
            product_environment: Deprecated alias for *product_registry*.
        """
        if product_registry is None:
            product_registry = product_environment
        super().__init__(product_registry=product_registry, workspace=workspace)


__all__ = ["QueryFactory", "SearchPlanner"]
