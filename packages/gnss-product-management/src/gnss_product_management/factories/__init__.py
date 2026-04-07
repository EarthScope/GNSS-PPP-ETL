"""Author: Franklyn Dunbar

Factories — Layer 2: query construction, resource discovery, and file fetching.
"""

from gnss_product_management.factories.resource_factory import ResourceFactory
from gnss_product_management.factories.remote_factory import RemoteResourceFactory
from gnss_product_management.factories.query_factory import QueryFactory
from gnss_product_management.factories.resource_fetcher import (
    ResourceFetcher,
    FetchResult,
)
from gnss_product_management.specifications.dependencies.dependencies import (
    SearchPreference,
)
from gnss_product_management.environments import ProductEnvironment
from gnss_product_management.environments import WorkSpace
from gnss_product_management.factories.dependency_resolver import DependencyResolver
from gnss_product_management.lockfile import DependencyLockFile

__all__ = [
    "ProductEnvironment",
    "WorkSpace",
    "DependencyResolver",
    "ResourceFactory",
    "RemoteResourceFactory",
    "QueryFactory",
    "ResourceFetcher",
    "FetchResult",
    "DependencyLockFile",
    "SearchPreference",
]
