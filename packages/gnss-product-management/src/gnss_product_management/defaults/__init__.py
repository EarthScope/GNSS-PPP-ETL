"""Default singleton instances for the GNSS PPP product environment.

Constructs pre-configured :data:`DefaultProductEnvironment` and
:data:`DefaultWorkSpace` from the bundled YAML specifications
shipped with the ``gnss-management-specs`` package.

Users who need a different spec set should build their own
:class:`ProductRegistry` via its ``add_*`` methods rather than
importing these defaults.
"""

from pathlib import Path

from gpm_specs.configs import (
    CENTERS_RESOURCE_DIR,
    FORMAT_SPEC_YAML,
    LOCAL_SPEC_DIR,
    META_SPEC_YAML,
    PRODUCT_SPEC_YAML,
)

from gnss_product_management.environments import ProductRegistry, WorkSpace

# Pre-built environment with all bundled parameter, format, product, and center specs.
DefaultProductEnvironment = ProductRegistry()
DefaultProductEnvironment.add_parameter_spec(META_SPEC_YAML)
DefaultProductEnvironment.add_format_spec(FORMAT_SPEC_YAML)
DefaultProductEnvironment.add_product_spec(PRODUCT_SPEC_YAML)
for path in Path(CENTERS_RESOURCE_DIR).glob("*.yaml"):
    DefaultProductEnvironment.add_resource_spec(path)
DefaultProductEnvironment.build()

# Workspace pre-loaded with local resource layout specs.
DefaultWorkSpace = WorkSpace()
for path in Path(LOCAL_SPEC_DIR).glob("*.yaml"):
    DefaultWorkSpace.add_resource_spec(path)
