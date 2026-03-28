from pathlib import Path

from gnss_ppp_products.defaults import DefaultProductEnvironment, DefaultWorkSpace
from gnss_ppp_products.specifications.dependencies.dependencies import DependencySpec

config_dir = Path(__file__).parent.parent / "configs"
PRIDE_PPPAR_SPEC = config_dir / "dependencies"/ "pride_pppar.yaml"
PRIDE_DIR_SPEC = config_dir / "local" / "pride_config.yaml"

DefaultWorkSpace.add_resource_spec(PRIDE_DIR_SPEC)
Pride_PPP_task = DependencySpec.from_yaml(PRIDE_PPPAR_SPEC)

__all__ = ["DefaultProductEnvironment", "DefaultWorkSpace", "Pride_PPP_task"]