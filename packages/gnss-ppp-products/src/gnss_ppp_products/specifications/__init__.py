"""
Specifications — pure, agnostic spec models and registry classes.

This package contains the Pydantic models and registry classes for all
GNSS product specifications.  No singletons are created here; no YAML
paths are hardcoded.  Registry classes accept data via their loaders and
callers provide explicit paths.

For the pre-built default singletons, import from
:mod:`gnss_ppp_products.configs.defaults` (or use the convenience
re-exports in the package ``__init__``).

Sub-packages
~~~~~~~~~~~~

- :mod:`.metadata`     — ``_MetadataRegistry``, ``MetadataField``
- :mod:`.products`     — ``_ProductSpecRegistry``, ``ProductSpec``
- :mod:`.remote`       — ``_RemoteResourceRegistry``, ``RemoteResourceSpec``
- :mod:`.local`        — ``_LocalResourceRegistry``, ``LocalResourceSpec``
- :mod:`.query`        — ``ProductQuery``, ``QueryResult``, ``QuerySpec``
- :mod:`.dependencies` — ``DependencyResolver``, ``DependencySpec``
"""

# ---- Registry classes (no singletons) ----
from gnss_ppp_products.specifications.metadata.registry import (
    _MetadataRegistry,
    MetadataField,
    extract_template_fields,
)
from gnss_ppp_products.specifications.products.models import (
    ProductSpec,
    Product,
    Format,
    FormatVersion,
    ProductFormatRef,
)
from gnss_ppp_products.specifications.products.registry import (
    _ProductSpecRegistry,
)
from gnss_ppp_products.specifications.remote.models import (
    Server,
    RemoteProduct,
    RemoteResourceSpec,
)
from gnss_ppp_products.specifications.remote.registry import (
    _RemoteResourceRegistry,
)
from gnss_ppp_products.specifications.local.models import (
    TemporalCategory,
    LocalCollection,
    LocalResourceSpec,
)
from gnss_ppp_products.specifications.local.registry import (
    _LocalResourceRegistry,
)
from gnss_ppp_products.specifications.query.models import (
    AxisDef,
    ExtraAxisDef,
    ProductQueryProfile,
    QuerySpec,
)
from gnss_ppp_products.specifications.query.engine import (
    ProductQuery,
    QueryResult,
    select_best_antex,
)
from gnss_ppp_products.specifications.dependencies.models import (
    SearchPreference,
    Dependency,
    DependencySpec,
    DependencyResolution,
    ResolvedDependency,
)

# DependencyResolver is NOT re-exported here to avoid triggering
# a server/__init__.py import chain at module load.  Import it
# directly: from gnss_ppp_products.specifications.dependencies.resolver import DependencyResolver

__all__ = [
    # metadata
    "_MetadataRegistry",
    "MetadataField",
    "extract_template_fields",
    # products
    "_ProductSpecRegistry",
    "ProductSpec",
    "Product",
    "Format",
    "FormatVersion",
    "ProductFormatRef",
    # remote
    "_RemoteResourceRegistry",
    "Server",
    "RemoteProduct",
    "RemoteResourceSpec",
    # local
    "_LocalResourceRegistry",
    "TemporalCategory",
    "LocalCollection",
    "LocalResourceSpec",
    # query
    "AxisDef",
    "ExtraAxisDef",
    "ProductQueryProfile",
    "QuerySpec",
    "ProductQuery",
    "QueryResult",
    "select_best_antex",
    # dependencies
    "SearchPreference",
    "Dependency",
    "DependencySpec",
    "DependencyResolution",
    "ResolvedDependency",
]
