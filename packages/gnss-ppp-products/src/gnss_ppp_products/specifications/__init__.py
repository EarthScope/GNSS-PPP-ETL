"""
Specifications — Layer 1: pure Pydantic models for GNSS product specs.

This package contains the data-shape definitions loaded from YAML.
No loading logic, no singletons, no cross-validation.

For the live registries and resolution logic, see
:mod:`gnss_ppp_products.catalogs`.

Modules
~~~~~~~
- :mod:`.metadata`     — ``MetadataField``
- :mod:`.formats`      — ``FormatFieldDef``, ``FormatSpec``, ``FormatVersionSpec``
- :mod:`.products`     — ``ProductFormatBinding``, ``ProductSpec``
- :mod:`.local`        — ``LocalCollection``, ``LocalResourceSpec``
- :mod:`.remote`       — ``ServerSpec``, ``RemoteProductSpec``, ``RemoteResourceSpec``
- :mod:`.query`        — ``AxisDef``, ``ExtraAxisDef``, ``ProductQueryProfile``
- :mod:`.dependencies` — ``SearchPreference``, ``Dependency``, ``DependencySpec``,
                         ``ResolvedDependency``, ``DependencyResolution``
"""

from gnss_ppp_products.specifications.metadata import MetadataField
from gnss_ppp_products.specifications.formats import (
    FormatFieldDef,
    FormatVersionSpec,
    FormatSpec,
)
from gnss_ppp_products.specifications.products import (
    ProductFormatBinding,
    ProductSpec,
)
from gnss_ppp_products.specifications.remote import (
    ServerSpec,
    RemoteProductSpec,
    RemoteResourceSpec,
)
from gnss_ppp_products.specifications.local import (
    LocalCollection,
    LocalResourceSpec,
)
from gnss_ppp_products.specifications.query import (
    AxisDef,
    ExtraAxisDef,
    ProductQueryProfile,
)
from gnss_ppp_products.specifications.dependencies import (
    SearchPreference,
    Dependency,
    DependencySpec,
    DependencyResolution,
    ResolvedDependency,
)

__all__ = [
    "MetadataField",
    "FormatFieldDef",
    "FormatVersionSpec",
    "FormatSpec",
    "ProductFormatBinding",
    "ProductSpec",
    "ServerSpec",
    "RemoteProductSpec",
    "RemoteResourceSpec",
    "LocalCollection",
    "LocalResourceSpec",
    "AxisDef",
    "ExtraAxisDef",
    "ProductQueryProfile",
    "SearchPreference",
    "Dependency",
    "DependencySpec",
    "DependencyResolution",
    "ResolvedDependency",
]
