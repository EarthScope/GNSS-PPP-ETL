"""
Query spec registry.

Loads ``query_v2.yaml`` at import time and exposes a module-level
``QuerySpecRegistry`` singleton.

Usage::

    from gnss_ppp_products.assets.query_spec import QuerySpecRegistry

    QuerySpecRegistry.spec_names      # ['ORBIT', 'CLOCK', ...]
    QuerySpecRegistry.profile("ORBIT")  # ProductQueryProfile(...)
    QuerySpecRegistry.axis_def("solution")  # AxisDef(...)
"""

from .query import QuerySpec

QuerySpecRegistry = QuerySpec.from_yaml()

from .engine import ProductQuery, QueryResult

__all__ = ["QuerySpecRegistry", "ProductQuery", "QueryResult"]
