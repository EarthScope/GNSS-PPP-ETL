"""GNSS PPP Products — specification-driven product discovery and resolution."""

# -- Primary public API -------------------------------------------------------
from gnss_product_management.client import FoundResource, GNSSClient, ProductQuery  # noqa: F401
from gnss_product_management.defaults import (  # noqa: F401
    DefaultProductEnvironment,
    DefaultWorkSpace,
)
from gnss_product_management.environments import ProductRegistry, WorkSpace  # noqa: F401

# -- Advanced / escape-hatch --------------------------------------------------
# These are available for power users who need direct access to the pipeline.
# Prefer GNSSClient for all standard use cases.
from gnss_product_management.factories import (  # noqa: F401
    DownloadPipeline,
    LockfileWriter,
    ResolvePipeline,
    SearchPlanner,
    SearchPreference,
    WormHole,
)
from gnss_product_management.specifications.dependencies.dependencies import (  # noqa: F401
    DependencyResolution,
    DependencySpec,
)
