from typing import Dict
from .models import LocalResourceSpec

class _LocalResourceRegistry:
    def __init__(self) -> None:
        self._specs: Dict[str, LocalResourceSpec] = {}
    
    def load_from_yaml(self, yaml_path: str | Path) -> None:
        """Load a single YAML spec file."""
        spec = LocalResourceSpec.from_yaml(yaml_path)
        self._specs[spec.id] = spec
      