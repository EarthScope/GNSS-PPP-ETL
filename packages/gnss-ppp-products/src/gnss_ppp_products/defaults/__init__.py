from pathlib import Path
from gnss_ppp_products.configs import (
    META_SPEC_YAML,
    FORMAT_SPEC_YAML,
    PRODUCT_SPEC_YAML,
    LOCAL_SPEC_DIR,
    CENTERS_RESOURCE_DIR,
    PRIDE_PPPAR_SPEC,
)
from gnss_ppp_products.environments import ProductEnvironment
from gnss_ppp_products.environments import WorkSpace
from gnss_ppp_products.specifications.dependencies.dependencies import DependencySpec

DefaultProductEnvironment = ProductEnvironment()
DefaultProductEnvironment.add_parameter_spec(META_SPEC_YAML)
DefaultProductEnvironment.add_format_spec(FORMAT_SPEC_YAML)
DefaultProductEnvironment.add_product_spec(PRODUCT_SPEC_YAML)
for path in Path(CENTERS_RESOURCE_DIR).glob("*.yaml"):
    DefaultProductEnvironment.add_resource_spec(path)
DefaultProductEnvironment.build()

DefaultWorkSpace = WorkSpace()
for path in Path(LOCAL_SPEC_DIR).glob("*.yaml"):
    DefaultWorkSpace.add_resource_spec(path)

Pride_PPP_task = DependencySpec.from_yaml(PRIDE_PPPAR_SPEC)
