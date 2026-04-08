"""Author: Franklyn Dunbar

GNSS PPP Products — specification-driven product discovery and resolution.
"""

from gnss_product_management.factories import (  # noqa: F401
    # New names
    ProductRegistry,
    WorkSpace,
    DependencyResolver,
    SearchPlanner,
    RemoteTransport,
    # Backward-compatible aliases
    ProductEnvironment,
    QueryFactory,
    ResourceFetcher,
)
