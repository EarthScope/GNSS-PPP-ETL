"""
Format catalog — loads and indexes format specifications from YAML.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Union

import yaml
from pydantic import BaseModel, Field

from gnss_ppp_products.specifications.formats import (
    FormatFieldDef,
    FormatSpec,
    FormatVersionSpec,
)


class FormatCatalog(BaseModel):
    """Read-only registry of reusable format definitions.

    Loaded from the ``formats:`` key of the product spec YAML.
    """

    formats: Dict[str, FormatSpec] = Field(default_factory=dict)

    def get_format(self, name: str) -> FormatSpec:
        try:
            return self.formats[name]
        except KeyError:
            raise KeyError(
                f"Format {name!r} not found. "
                f"Available: {sorted(self.formats)}"
            )

    def get_version(self, format_name: str, version: str) -> FormatVersionSpec:
        fmt = self.get_format(format_name)
        try:
            return fmt.versions[version]
        except KeyError:
            raise KeyError(
                f"Version {version!r} not found in format {format_name!r}. "
                f"Available: {sorted(fmt.versions)}"
            )

    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> "FormatCatalog":
        """Load from a YAML file, extracting the ``formats:`` section."""
        with open(path) as fh:
            raw = yaml.safe_load(fh)
        return cls.model_validate({"formats": raw.get("formats", {})})
