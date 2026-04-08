"""Author: Franklyn Dunbar

Factories — Layer 2: query construction, resource discovery, and file fetching.
"""

from gnss_product_management.factories.source_planner import SourcePlanner
from gnss_product_management.factories.remote_search_planner import RemoteSearchPlanner
from gnss_product_management.factories.search_planner import SearchPlanner
from gnss_product_management.factories.remote_transport import RemoteTransport
from gnss_product_management.environments import ProductRegistry, ProductEnvironment
from gnss_product_management.environments import WorkSpace
from gnss_product_management.factories.dependency_resolver import DependencyResolver
from gnss_product_management.lockfile import DependencyLockFile
from gnss_product_management.specifications.dependencies.dependencies import (
    SearchPreference,
)

# Backward-compatible aliases
from gnss_product_management.factories.resource_factory import ResourceFactory
from gnss_product_management.factories.remote_factory import RemoteResourceFactory
from gnss_product_management.factories.query_factory import QueryFactory
from gnss_product_management.factories.resource_fetcher import (
    ResourceFetcher,
    FetchResult,
)

__all__ = [
    # New names
    "ProductRegistry",
    "WorkSpace",
    "DependencyResolver",
    "SourcePlanner",
    "RemoteSearchPlanner",
    "SearchPlanner",
    "RemoteTransport",
    "DependencyLockFile",
    "SearchPreference",
    # Backward-compatible aliases
    "ProductEnvironment",
    "ResourceFactory",
    "RemoteResourceFactory",
    "QueryFactory",
    "ResourceFetcher",
    "FetchResult",
]
