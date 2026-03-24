"""Factories — Layer 2: query construction, resource discovery, and file fetching."""

from gnss_ppp_products.factories.resource_factory import ResourceFactory
from gnss_ppp_products.factories.remote_factory import RemoteResourceFactory
from gnss_ppp_products.factories.query_factory import QueryFactory
from gnss_ppp_products.factories.resource_fetcher import ResourceFetcher, FetchResult
from gnss_ppp_products.factories.environment import ProductEnvironment
from gnss_ppp_products.factories.models import (
    DiscoveryEntry,
    DiscoveryReport,
    FoundResource,
    MissingProductError,
    Resolution,
)

__all__ = [
    "ProductEnvironment",
    "ResourceFactory",
    "RemoteResourceFactory",
    "QueryFactory",
    "ResourceFetcher",
    "FetchResult",
    "DiscoveryEntry",
    "DiscoveryReport",
    "FoundResource",
    "MissingProductError",
    "Resolution",
]
