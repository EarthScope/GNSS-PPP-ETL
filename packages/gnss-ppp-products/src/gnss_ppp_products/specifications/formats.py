"""Pure Pydantic models for format specifications."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FormatFieldDef(BaseModel):
    """Properties of a metadata field declared inside a format version."""

    pattern: Optional[str] = None
    default: Optional[str] = None
    description: Optional[str] = None


class FormatVersionSpec(BaseModel):
    """A single version of a format (e.g. RINEX v3, PRODUCT v1)."""

    model_config = ConfigDict(extra="allow")

    description: Optional[str] = None
    notes: Optional[str] = None
    metadata: Dict[str, Optional[FormatFieldDef]] = Field(default_factory=dict)
    file_templates: Dict[str, str] = Field(default_factory=dict)
    compression: List[str] = Field(default_factory=list)

    @field_validator("file_templates", mode="before")
    @classmethod
    def _unwrap_lists(cls, v: Dict) -> Dict[str, str]:
        """Accept both ``str`` and ``[str]`` from YAML."""
        out: Dict[str, str] = {}
        for key, val in v.items():
            if isinstance(val, list):
                out[key] = val[0] if val else ""
            else:
                out[key] = val
        return out

    def get_field_defaults(self) -> Dict[str, str]:
        """Return ``{name: default_pattern}`` for fields with a default."""
        defaults: Dict[str, str] = {}
        for name, field_def in self.metadata.items():
            if field_def is not None and field_def.default is not None:
                defaults[name] = field_def.default
        return defaults


class FormatSpec(BaseModel):
    """A top-level format definition (e.g. RINEX, PRODUCT, TABLE)."""

    description: str = ""
    versions: Dict[str, FormatVersionSpec] = Field(default_factory=dict)
    compression: List[str] = Field(default_factory=list)

    def get_compression(self, version: str) -> List[str]:
        """Return compression for *version*, falling back to format-level."""
        ver = self.versions.get(version)
        if ver and ver.compression:
            return ver.compression
        return self.compression
