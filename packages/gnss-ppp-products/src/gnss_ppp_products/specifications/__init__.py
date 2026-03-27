"""
Specifications — Layer 1: Pydantic models and resolution logic for GNSS product specs.

Subpackages
~~~~~~~~~~~
- :mod:`.parameters`   — ``Parameter``, ``ParameterCatalog``
- :mod:`.format`       — ``FormatFieldDef``, ``FormatVersionSpec``, ``FormatSpec``,
                         ``FormatCatalog``, ``FormatSpecCatalog``
- :mod:`.products`     — ``Product``, ``ProductPath``, ``ProductCatalog``
- :mod:`.local`        — ``LocalCollection``, ``LocalResourceSpec``
- :mod:`.remote`       — ``Server``, ``ResourceSpec``, ``ResourceQuery``,
                         ``ResourceCatalog``
- :mod:`.dependencies` — ``DependencySpec``, ``ResolvedDependency``,
                         ``LockProduct``, ``ProductLockfile``
"""

from gnss_ppp_products.specifications.catalog import Catalog
from gnss_ppp_products.specifications.parameters.parameter import (
    Parameter,
    ParameterCatalog,
)
from gnss_ppp_products.specifications.format.spec import (
    FormatFieldDef,
    FormatVersionSpec,
    FormatSpec,
    FormatSpecCollection,
)
from gnss_ppp_products.specifications.format.format_spec import (
    FormatCatalog,
    FormatSpecCatalog,
)
from gnss_ppp_products.specifications.products.product import (
    Product,
    ProductPath,
)
from gnss_ppp_products.specifications.products.catalog import (
    ProductCatalog,
    ProductSpecCatalog,
)
from gnss_ppp_products.specifications.remote.resource import (
    Server,
    ResourceSpec,
    ResourceQuery,
)
from gnss_ppp_products.specifications.remote.resource_catalog import (
    ResourceCatalog,
)
from gnss_ppp_products.specifications.local.local import (
    LocalCollection,
    LocalResourceSpec,
)
from gnss_ppp_products.specifications.dependencies.dependencies import (
    SearchPreference,
    Dependency,
    DependencySpec,
    DependencyResolution,
    ResolvedDependency,
)
from gnss_ppp_products.specifications.dependencies.lockfile import (
    LockProduct,
    LockProductAlternative,
    ProductLockfile,
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
    "FormatCatalog",
    "FormatSpecCatalog",
    # products
    "Product",
    "ProductPath",
    "ProductCatalog",
    "ProductSpecCatalog",
    # remote
    "Server",
    "ResourceSpec",
    "ResourceQuery",
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
    "ProductLockfile",
]
