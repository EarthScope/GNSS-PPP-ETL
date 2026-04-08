"""Author: Franklyn Dunbar

RemoteResourceFactory — backward-compatible alias for RemoteSearchPlanner.

.. deprecated::
    Import :class:`RemoteSearchPlanner` from
    ``gnss_product_management.factories.remote_search_planner`` instead.
"""

from gnss_product_management.factories.remote_search_planner import RemoteSearchPlanner

# Backward-compatible alias
RemoteResourceFactory = RemoteSearchPlanner

__all__ = ["RemoteResourceFactory", "RemoteSearchPlanner"]
