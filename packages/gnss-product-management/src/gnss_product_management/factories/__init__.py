"""Author: Franklyn Dunbar

Factories — Layer 2: query construction, resource discovery, and file fetching.
"""

from gnss_product_management.factories.source_planner import SourcePlanner
from gnss_product_management.factories.search_planner import SearchPlanner
from gnss_product_management.factories.remote_transport import WormHole
from gnss_product_management.environments import ProductRegistry
from gnss_product_management.environments import WorkSpace
from gnss_product_management.factories.dependency_resolver import DependencyResolver
from gnss_product_management.lockfile import DependencyLockFile
from gnss_product_management.specifications.dependencies.dependencies import (
    SearchPreference,
)
from gnss_product_management.factories.pipelines import (
    FindPipeline,
    DownloadPipeline,
    LockfileWriter,
    ResolvePipeline,
)

__all__ = [
    "ProductRegistry",
    "WorkSpace",
    "DependencyResolver",
    "SourcePlanner",
    "SearchPlanner",
    "WormHole",
    "DependencyLockFile",
    "SearchPreference",
    "FindPipeline",
    "DownloadPipeline",
    "LockfileWriter",
    "ResolvePipeline",
]
