"""Author: Franklyn Dunbar

ResourceFactory — backward-compatible alias for SourcePlanner.

.. deprecated::
    Import :class:`SourcePlanner` from
    ``gnss_product_management.factories.source_planner`` instead.
"""

from gnss_product_management.factories.source_planner import SourcePlanner

# Backward-compatible alias
ResourceFactory = SourcePlanner

__all__ = ["ResourceFactory", "SourcePlanner"]
