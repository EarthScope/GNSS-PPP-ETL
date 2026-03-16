"""
Dependency specification — declare what products a task needs and
where to search for them.

Public API::

    from gnss_ppp_products.assets.dependency_spec import (
        DependencySpec,
        DependencyResolver,
        DependencyResolution,
        ResolvedDependency,
    )
"""

from .models import (
    Dependency,
    DependencyResolution,
    DependencySpec,
    ResolvedDependency,
    SearchPreference,
)
from .resolver import DependencyResolver

__all__ = [
    "Dependency",
    "DependencyResolution",
    "DependencyResolver",
    "DependencySpec",
    "ResolvedDependency",
    "SearchPreference",
]
