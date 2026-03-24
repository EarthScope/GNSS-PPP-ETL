"""Factories — Layer 2: query construction, resource discovery, and file fetching."""

from gnss_ppp_products.factories.remote_factory import RemoteResourceFactory
from gnss_ppp_products.factories.query_factory import QueryFactory, QueryProfile, AxisAlias, SortPreference
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
    "RemoteResourceFactory",
    "QueryFactory",
    "QueryProfile",
    "AxisAlias",
    "SortPreference",
    "ResourceFetcher",
    "FetchResult",
    "DiscoveryEntry",
    "DiscoveryReport",
    "FoundResource",
    "MissingProductError",
    "Resolution",
]
