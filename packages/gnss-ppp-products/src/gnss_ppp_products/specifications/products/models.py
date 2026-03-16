"""
Pydantic models for the GNSS product specification schema.

These classes mirror the structure defined in ``product_spec.yaml`` and
provide typed, validated access to campaigns, solutions, content types,
format definitions, and product declarations.

Usage::

    spec = ProductSpec.from_yaml("/path/to/product_spec.yaml")
    orbit = spec.products["ORBIT"]
    rinex_fmt = spec.formats["RINEX"]
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field


# ===================================================================
# Format-level models
# ===================================================================


class FormatVersion(BaseModel):
    """A single version of a format (e.g. RINEX v2, PRODUCT v1)."""

    model_config = ConfigDict(extra="allow")

    description: Optional[str] = None
    notes: Optional[str] = None
    metadata: List[Union[str, Dict]] = Field(default_factory=list)
    filename: Dict[str, List[str]] = Field(default_factory=dict)
    compression: List[str] = Field(default_factory=list)

    def get_metadata_overrides(self) -> Dict[str, str]:
        """Extract format-level regex overrides from the metadata list."""
        overrides: Dict[str, str] = {}
        for entry in self.metadata:
            if isinstance(entry, dict):
                for field, value in entry.items():
                    if isinstance(value, dict) and "default" in value:
                        overrides[field] = value["default"]
        return overrides


class Format(BaseModel):
    """A top-level format definition (e.g. RINEX, PRODUCT, TABLE)."""

    description: str = ""
    versions: Dict[str, FormatVersion] = Field(default_factory=dict)
    compression: List[str] = Field(default_factory=list)

    def get_compression(self, version: str) -> List[str]:
        """Return compression list for *version*, falling back to format-level."""
        ver = self.versions.get(version)
        if ver and ver.compression:
            return ver.compression
        return self.compression


# ===================================================================
# Product-level models
# ===================================================================


class ProductFormatRef(BaseModel):
    """A reference from a product to a specific format + version."""

    format: str
    version: str
    metadata: List[Dict[str, str]] = Field(default_factory=list)
    filename: Union[str, Dict[str, List[str]]] = "default"


class Product(BaseModel):
    """A product definition (e.g. ORBIT, CLOCK, RINEX_NAV)."""

    description: str = ""
    formats: List[ProductFormatRef] = Field(default_factory=list)


# ===================================================================
# Root model
# ===================================================================


class ProductSpec(BaseModel):
    """Root model for the full ``product_spec.yaml`` schema."""

    campaigns: List[str] = Field(default_factory=list)
    solutions: List[str] = Field(default_factory=list)
    content_types: List[str] = Field(default_factory=list)
    format_types: List[str] = Field(default_factory=list)
    metadata_defaults: Dict[str, str] = Field(default_factory=dict)
    formats: Dict[str, Format] = Field(default_factory=dict)
    products: Dict[str, Product] = Field(default_factory=dict)

    # ------------------------------------------------------------------
    # Loaders
    # ------------------------------------------------------------------

    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> "ProductSpec":
        """Load a ``ProductSpec`` from a YAML file."""
        with open(path) as fh:
            raw = yaml.safe_load(fh)
        return cls.model_validate(raw)

    # ------------------------------------------------------------------
    # Convenience look-ups
    # ------------------------------------------------------------------

    def get_format(self, name: str) -> Format:
        return self.formats[name]

    def get_product(self, name: str) -> Product:
        return self.products[name]

    def resolve_filename_templates(
        self,
        product_name: str,
        ref_index: int = 0,
    ) -> List[str]:
        """Return the concrete filename template(s) for a product format ref."""
        product = self.products[product_name]
        ref = product.formats[ref_index]
        fmt = self.formats[ref.format]
        ver = fmt.versions[ref.version]

        if isinstance(ref.filename, str):
            return ver.filename.get(ref.filename, [])
        templates: List[str] = []
        for patterns in ref.filename.values():
            templates.extend(patterns)
        return templates

    def resolve_metadata_constraints(
        self,
        product_name: str,
        ref_index: int = 0,
    ) -> Dict[str, str]:
        """Flatten a product format ref's metadata list into ``{field: pattern}``."""
        product = self.products[product_name]
        ref = product.formats[ref_index]
        merged: Dict[str, str] = {}
        for entry in ref.metadata:
            merged.update(entry)
        return merged

    def to_regex(
        self,
        product_name: str,
        ref_index: int = 0,
    ) -> List[str]:
        """Build filename regex(es) for a product format reference.

        Uses ``metadata_defaults`` for default patterns.
        """
        templates = self.resolve_filename_templates(product_name, ref_index)
        constraints = self.resolve_metadata_constraints(product_name, ref_index)

        product = self.products[product_name]
        ref = product.formats[ref_index]
        fmt = self.formats[ref.format]
        ver = fmt.versions[ref.version]
        format_overrides = ver.get_metadata_overrides()

        _PLACEHOLDER = re.compile(r"\{([^}]+)\}")

        def _ci_get(mapping: Dict[str, str], key: str) -> Optional[str]:
            if key in mapping:
                return mapping[key]
            key_lower = key.lower()
            for k, v in mapping.items():
                if k.lower() == key_lower:
                    return v
            return None

        _WB = re.compile(r"\\b")

        def _strip_wb(pattern: str) -> str:
            return _WB.sub("", pattern)

        regexes: List[str] = []

        for tmpl in templates:
            parts: List[str] = []
            last_end = 0
            for m in _PLACEHOLDER.finditer(tmpl):
                literal = re.escape(tmpl[last_end : m.start()])
                parts.append(literal.replace(r"\.\*", ".*").replace(r"\*", ".*"))

                field = m.group(1)
                hit = _ci_get(constraints, field)
                if hit is None:
                    hit = _ci_get(format_overrides, field)
                if hit is None:
                    hit = _ci_get(self.metadata_defaults, field)
                parts.append(_strip_wb(hit) if hit is not None else ".+")
                last_end = m.end()

            trailing = re.escape(tmpl[last_end:])
            parts.append(trailing.replace(r"\.\*", ".*").replace(r"\*", ".*"))
            regexes.append("".join(parts))

        return regexes
