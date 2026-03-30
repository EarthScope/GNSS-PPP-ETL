"""Author: Franklyn Dunbar

Environments — setup and configuration for product resolution.

Provides the two core configuration objects:

- :class:`ProductEnvironment` — loads YAML specs and builds the full catalog
  chain (parameters → formats → products → remote resource factory).
- :class:`WorkSpace` — registers local storage directories and maps them
  to :class:`LocalResourceSpec` layouts.
"""

from gnss_product_management.environments.environment import ProductEnvironment
from gnss_product_management.environments.workspace import (
    WorkSpace,
    RegisteredLocalResource,
    paths_overlap,
)

__all__ = [
    "ProductEnvironment",
    "WorkSpace",
    "RegisteredLocalResource",
    "paths_overlap",
]
