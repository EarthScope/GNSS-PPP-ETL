"""Author: Franklyn Dunbar

Environments — setup and configuration for product resolution.

Provides the two core configuration objects:

- :class:`ProductRegistry` — loads YAML specs and builds the full catalog
  chain (parameters → formats → products → remote search planner).
- :class:`WorkSpace` — registers local storage directories and maps them
  to :class:`LocalResourceSpec` layouts.
"""

from gnss_product_management.environments.environment import ProductRegistry
from gnss_product_management.environments.workspace import (
    RegisteredLocalResource,
    WorkSpace,
    paths_overlap,
)

__all__ = [
    "ProductRegistry",
    "WorkSpace",
    "RegisteredLocalResource",
    "paths_overlap",
]
