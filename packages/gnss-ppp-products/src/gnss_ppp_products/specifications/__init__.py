"""
Specifications — Layer 1: Pydantic models and resolution logic for GNSS product specs.

Subpackages
~~~~~~~~~~~
- :mod:`.parameters`   — ``Parameter``, ``ParameterCatalog``
- :mod:`.format`       — ``FormatFieldDef``, ``FormatVersionSpec``, ``FormatSpec``,
                         ``FormatCatalog``, ``FormatSpecCatalog``
- :mod:`.products`     — ``Product``, ``ProductPath``, ``ProductCatalog``
- :mod:`.local`        — ``LocalCollection``, ``LocalResourceSpec``,
                         ``LocalResourceFactory``
- :mod:`.remote`       — ``Server``, ``ResourceSpec``, ``ResourceQuery``,
                         ``RemoteResourceSpec``
- :mod:`.dependencies` — ``DependencySpec``, ``DependencyResolver``,
                         ``ResolvedDependency``, ``LockProduct``, ``ProductLockfile``
"""

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
from gnss_ppp_products.specifications.remote.remote import (
    ServerSpec,
    RemoteProductSpec,
    RemoteResourceSpec,
)
from gnss_ppp_products.specifications.remote.resource import (
    Server,
    ResourceSpec,
    ResourceQuery,
    ResourceCatalog,
)
from gnss_ppp_products.specifications.local.local import (
    LocalCollection,
    LocalResourceSpec,
)
from gnss_ppp_products.specifications.local.factory import (
    LocalResourceFactory,
)
from gnss_ppp_products.specifications.dependencies.dependencies import (
    SearchPreference,
    Dependency,
    DependencySpec,
    DependencyResolution,
    ResolvedDependency,
)
from gnss_ppp_products.specifications.dependencies.dependency_resolver import (
    DependencyResolver,
)
from gnss_ppp_products.specifications.dependencies.lockfile import (
    LockProduct,
    LockProductAlternative,
    ProductLockfile,
)

__all__ = [
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
    "ServerSpec",
    "RemoteProductSpec",
    "RemoteResourceSpec",
    "Server",
    "ResourceSpec",
    "ResourceQuery",
    "ResourceCatalog",
    # local
    "LocalCollection",
    "LocalResourceSpec",
    "LocalResourceFactory",
    # dependencies
    "SearchPreference",
    "Dependency",
    "DependencySpec",
    "DependencyResolution",
    "ResolvedDependency",
    "DependencyResolver",
    "LockProduct",
    "LockProductAlternative",
    "ProductLockfile",
]
