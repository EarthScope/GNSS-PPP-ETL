"""Dependency specification — models and resolver."""

from .models import (
    SearchPreference,
    Dependency,
    DependencySpec,
    ResolvedDependency,
    DependencyResolution,
)

# DependencyResolver uses gnss_ppp_products.server.ftp/http which can
# trigger heavy v1 import chains.  Import it explicitly when needed:
#   from gnss_ppp_products.specifications.dependencies.resolver import DependencyResolver

__all__ = [
    "SearchPreference",
    "Dependency",
    "DependencySpec",
    "ResolvedDependency",
    "DependencyResolution",
]
