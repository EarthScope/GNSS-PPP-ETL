"""Author: Franklyn Dunbar

Default singleton instances for the GNSS PPP product environment.

Constructs pre-configured :data:`DefaultProductEnvironment` and
:data:`DefaultWorkSpace` from the bundled YAML specifications
shipped with the package.
"""

from pathlib import Path
from gnss_management_specs.configs import (
    META_SPEC_YAML,
    FORMAT_SPEC_YAML,
    PRODUCT_SPEC_YAML,
    LOCAL_SPEC_DIR,
    CENTERS_RESOURCE_DIR,
)
from gnss_product_management.environments import ProductEnvironment
from gnss_product_management.environments import WorkSpace

# Pre-built environment with all bundled parameter, format, product, and center specs.
DefaultProductEnvironment = ProductEnvironment()
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
