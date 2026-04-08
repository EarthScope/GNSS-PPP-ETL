"""Author: Franklyn Dunbar

Specifications — Layer 1: Pydantic models and resolution logic for GNSS product specs.

Subpackages
~~~~~~~~~~~
- :mod:`.parameters`   — ``Parameter``, ``ParameterCatalog``
- :mod:`.format`       — ``FormatFieldDef``, ``FormatVersionSpec``, ``FormatSpec``,
                         ``FormatCatalog``, ``FormatSpecCatalog``
- :mod:`.products`     — ``Product``, ``PathTemplate``, ``ProductCatalog``
- :mod:`.local`        — ``LocalCollection``, ``LocalResourceSpec``
- :mod:`.remote`       — ``Server``, ``ResourceSpec``, ``SearchTarget``,
                         ``ResourceCatalog``
- :mod:`.dependencies` — ``DependencySpec``, ``ResolvedDependency``

Lockfile models (``LockProduct``, ``DependencyLockFile``) live in
:mod:`gnss_product_management.lockfile` but are re-exported here for convenience.
"""

from gnss_product_management.specifications.catalog import Catalog
from gnss_product_management.specifications.parameters.parameter import (
    Parameter,
    ParameterCatalog,
)
from gnss_product_management.specifications.format.spec import (
    FormatFieldDef,
    FormatVersionSpec,
    FormatSpec,
    FormatSpecCollection,
    FormatRegistry,
)
from gnss_product_management.specifications.format.format_spec import (
    FormatVariantSpec,
    FormatCatalog,
    FormatSpecCatalog,
)
from gnss_product_management.specifications.products.product import (
    Product,
    PathTemplate,
)
from gnss_product_management.specifications.products.catalog import (
    ProductCatalog,
    ProductSpecCatalog,
)
from gnss_product_management.specifications.remote.resource import (
    Server,
    ResourceSpec,
    SearchTarget,
)
from gnss_product_management.specifications.remote.resource_catalog import (
    ResourceCatalog,
)
from gnss_product_management.specifications.local.local import (
    LocalCollection,
    LocalResourceSpec,
)
from gnss_product_management.specifications.dependencies.dependencies import (
    SearchPreference,
    Dependency,
    DependencySpec,
    DependencyResolution,
    ResolvedDependency,
)
from gnss_product_management.lockfile import (
    LockProduct,
    LockProductAlternative,
    DependencyLockFile,
)

__all__ = [
    # base
    "Catalog",
    # parameters
    "Parameter",
    "ParameterCatalog",
    # format specs
    "FormatFieldDef",
    "FormatVersionSpec",
    "FormatSpec",
    "FormatSpecCollection",
    "FormatRegistry",
    "FormatVariantSpec",
    "FormatCatalog",
    "FormatSpecCatalog",
    # products
    "Product",
    "PathTemplate",
    "ProductCatalog",
    "ProductSpecCatalog",
    # remote
    "Server",
    "ResourceSpec",
    "SearchTarget",
    "ResourceCatalog",
    # local
    "LocalCollection",
    "LocalResourceSpec",
    # dependencies
    "SearchPreference",
    "Dependency",
    "DependencySpec",
    "DependencyResolution",
    "ResolvedDependency",
    "LockProduct",
    "LockProductAlternative",
    "DependencyLockFile",
]
