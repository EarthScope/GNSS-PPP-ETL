"""
Catalogs — Layer 2: load specs from YAML, cross-validate, resolve.

This package sits alongside ``specifications/`` (pure models) and
provides the live registries, factories, and engines that downstream
code (environment, configs) interacts with.
"""

from .metadata_catalog import MetadataCatalog, extract_template_fields
from .format_catalog import FormatCatalog
from .product_catalog import (
    ProductCatalog,
    ProductVariant,
    ProductResolver,
    ProductSpecRegistry,
)
from .local_factory import LocalResourceFactory
from .remote_factory import RemoteResourceFactory
from .query_engine import ProductQuery, QueryResult, QuerySpec, select_best_antex
from .dependency_resolver import DependencyResolver
from .validation import validate_catalogs

__all__ = [
    # metadata
    "MetadataCatalog",
    "extract_template_fields",
    # formats
    "FormatCatalog",
    # products
    "ProductCatalog",
    "ProductVariant",
    "ProductResolver",
    "ProductSpecRegistry",
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
