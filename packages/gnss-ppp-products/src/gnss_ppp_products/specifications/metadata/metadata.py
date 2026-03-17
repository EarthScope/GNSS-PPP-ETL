"""Pure Pydantic model for metadata field declarations."""
import yaml
from pathlib import Path
import datetime
from typing import Callable, Optional

from pydantic import BaseModel


class MetadataField(BaseModel):
    """A single registered metadata key."""

    name: str
    pattern: Optional[str] = None
    compute: Optional[Callable[[datetime.datetime], str]] = None
    description: Optional[str] = None

class MetadataSpec(BaseModel):
    """Full metadata specification for a processing task."""

    fields: dict[str, MetadataField] = {}

    @classmethod
    def from_yaml(cls, yaml_path: str | Path) -> "MetadataSpec":
        """Load metadata field definitions from a YAML file.

        Does **not** register computed fields — call
        :func:`register_computed_fields` separately after loading.
        """
        catalog = cls()

        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)

        for name, entries in data.items():
            pattern = None
            description = ""
            for entry in entries:
                if "pattern" in entry:
                    pattern = entry["pattern"]
                if "description" in entry:
                    description = entry["description"]

            if pattern is not None:
                catalog.register(name, pattern, description=description)
        return catalog
