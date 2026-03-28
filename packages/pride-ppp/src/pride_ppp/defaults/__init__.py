from pathlib import Path

from gnss_ppp_products.defaults import DefaultWorkSpace
from gnss_ppp_products.configs import (
    META_SPEC_YAML,
    FORMAT_SPEC_YAML,
    PRODUCT_SPEC_YAML,
    CENTERS_RESOURCE_DIR,
)
from gnss_ppp_products.environments import ProductEnvironment
from gnss_ppp_products.specifications.dependencies.dependencies import DependencySpec

config_dir = Path(__file__).parent.parent / "configs"
PRIDE_PPPAR_SPEC = config_dir / "dependencies" / "pride_pppar.yaml"
PRIDE_DIR_SPEC = config_dir / "local" / "pride_config.yaml"
PRIDE_INSTALL_SPEC = config_dir / "local" / "pride_install_config.yaml"
PRIDE_PRODUCT_SPEC = config_dir / "products" / "pride_product_spec.yaml"
PRIDE_CENTERS_DIR = config_dir / "centers"

# Build a ProductEnvironment that extends the base with PRIDE-specific
# static table products (file_name, FES2004S1.dat, gpt3_1.grd, etc.).
DefaultProductEnvironment = ProductEnvironment()
DefaultProductEnvironment.add_parameter_spec(META_SPEC_YAML)
DefaultProductEnvironment.add_format_spec(FORMAT_SPEC_YAML)
DefaultProductEnvironment.add_product_spec(PRODUCT_SPEC_YAML)
DefaultProductEnvironment.add_product_spec(PRIDE_PRODUCT_SPEC, id="pride")
for path in Path(CENTERS_RESOURCE_DIR).glob("*.yaml"):
    DefaultProductEnvironment.add_resource_spec(path)
for path in PRIDE_CENTERS_DIR.glob("*.yaml"):
    DefaultProductEnvironment.add_resource_spec(path)
DefaultProductEnvironment.build()

DefaultWorkSpace.add_resource_spec(PRIDE_DIR_SPEC)
DefaultWorkSpace.add_resource_spec(PRIDE_INSTALL_SPEC)
Pride_PPP_task = DependencySpec.from_yaml(PRIDE_PPPAR_SPEC)

__all__ = ["DefaultProductEnvironment", "DefaultWorkSpace", "Pride_PPP_task"]