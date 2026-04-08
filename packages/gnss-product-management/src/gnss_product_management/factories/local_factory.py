"""Author: Franklyn Dunbar

LocalResourceFactory — backward-compatible alias for LocalSearchPlanner.

.. deprecated::
    Import :class:`LocalSearchPlanner` from
    ``gnss_product_management.factories.local_search_planner`` instead.
"""

from gnss_product_management.factories.local_search_planner import LocalSearchPlanner

# Backward-compatible alias
LocalResourceFactory = LocalSearchPlanner

__all__ = ["LocalResourceFactory", "LocalSearchPlanner"]
