"""
Catalogs — Layer 2: load specs from YAML, cross-validate, resolve.

This package sits alongside ``specifications/`` (pure models) and
provides the live registries, factories, and engines that downstream
code (environment, configs) interacts with.
"""

from ..specifications.metadata.metadata_catalog import MetadataCatalog, extract_template_fields
from ..specifications.format.format_catalog import FormatCatalog
from ..specifications.products.product_catalog import (
    ProductSpecCatalog,
    ProductVariant,
    ProductCatalog,
)
from ..specifications.local.local_factory import LocalResourceFactory
from ..specifications.remote.remote_factory import RemoteResourceFactory
from ..specifications.queries.query_engine import ProductQuery, QueryResult, QuerySpec, select_best_antex
from ..specifications.dependencies.dependency_resolver import DependencyResolver
from .validation import validate_catalogs

__all__ = [
    # metadata
    "MetadataCatalog",
    "extract_template_fields",
    # formats
    "FormatCatalog",
    # products
    "ProductSpecCatalog",
    "ProductVariant",
    "ProductCatalog",
    # local
    "LocalResourceFactory",
    # remote
    "RemoteResourceFactory",
    # query
    "ProductQuery",
    "QueryResult",
    "QuerySpec",
    "select_best_antex",
    # dependencies
    "DependencyResolver",
    # validation
    "validate_catalogs",
]
