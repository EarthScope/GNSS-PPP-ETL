"""
Pydantic models for the GNSS product specification schema.

These classes mirror the structure defined in ``product_spec.yaml`` and
provide typed, validated access to campaigns, solutions, content types,
format definitions, and product declarations.

Usage::

    spec = ProductSpec.from_yaml()          # loads bundled product_spec.yaml
    spec = ProductSpec.from_yaml("/path/to/custom.yaml")

    orbit = spec.products["ORBIT"]
    rinex_fmt = spec.formats["RINEX"]
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Default YAML path (sibling config_files directory)
# ---------------------------------------------------------------------------

_DEFAULT_YAML = (
    Path(__file__).resolve().parent / "product_spec.yaml"
)


# ===================================================================
# Format-level models
# ===================================================================


class FormatVersion(BaseModel):
    """A single version of a format (e.g. RINEX v2, PRODUCT v1).

    Attributes
    ----------
    description : str, optional
        Human-readable description of this version.
    notes : str, optional
        Additional notes about this version.
    metadata : list[str | dict]
        Ordered list of metadata field declarations.  Each entry is
        either a plain string (field name, uses the root
        ``metadata_defaults`` regex) or a dict
        ``{FIELD: {"default": "<regex>"}}`` that overrides the root
        default for this format version.
    filename : dict[str, list[str]]
        Mapping of filename category (e.g. ``"observation"``,
        ``"default"``) to a list of filename template strings.
    compression : list[str]
        Supported compression suffixes (e.g. ``[".gz", ".Z"]``).
    """

    model_config = ConfigDict(extra="allow")

    description: Optional[str] = None
    notes: Optional[str] = None
    metadata: List[Union[str, Dict]] = Field(default_factory=list)
    filename: Dict[str, List[str]] = Field(default_factory=dict)
    compression: List[str] = Field(default_factory=list)

    def get_metadata_overrides(self) -> Dict[str, str]:
        """Extract format-level regex overrides from the metadata list.

        Returns
        -------
        dict[str, str]
            ``{field_name: regex}`` for every field that declares a
            ``default`` override at the format-version level.
        """
        overrides: Dict[str, str] = {}
        for entry in self.metadata:
            if isinstance(entry, dict):
                for field, value in entry.items():
                    if isinstance(value, dict) and "default" in value:
                        overrides[field] = value["default"]
        return overrides


class Format(BaseModel):
    """A top-level format definition (e.g. RINEX, PRODUCT, TABLE).

    Attributes
    ----------
    description : str
        Human-readable description of this format family.
    versions : dict[str, FormatVersion]
        Keyed by version string (``"2"``, ``"3"``, ``"1"``, …).
    compression : list[str]
        Format-wide compression suffixes.  Version-level compression
        takes precedence when present.
    """

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
    """A reference from a product to a specific format + version.

    Attributes
    ----------
    format : str
        Name of the parent format (e.g. ``"RINEX"``, ``"PRODUCT"``).
    version : str
        Version key within that format (e.g. ``"3"``, ``"1"``).
    metadata : list[dict[str, str]]
        Metadata field constraints for this product.  Each dict is a
        single ``{field: pattern}`` pair — the *pattern* is either a
        literal value (``"ORB"``) or a regex (``"\\b[GRECEJSM]\\b"``).
    filename : str or dict[str, list[str]]
        Either a string referencing a filename category defined in the
        parent format version (e.g. ``"navigation"``, ``"default"``),
        or a dict providing direct filename templates that override the
        format-level ones.
    """

    format: str
    version: str
    metadata: List[Dict[str, str]] = Field(default_factory=list)
    filename: Union[str, Dict[str, List[str]]] = "default"


class Product(BaseModel):
    """A product definition (e.g. ORBIT, CLOCK, RINEX_NAV).

    Attributes
    ----------
    description : str
        Human-readable description.
    formats : list[ProductFormatRef]
        One or more format references that can represent this product.
    """

    description: str = ""
    formats: List[ProductFormatRef] = Field(default_factory=list)


# ===================================================================
# Root model
# ===================================================================


class ProductSpec(BaseModel):
    """Root model for the full ``product_spec.yaml`` schema.

    Attributes
    ----------
    campaigns : list[str]
        Valid campaign codes (e.g. ``"DEM"``, ``"MGX"``).
    solutions : list[str]
        Valid solution type codes (e.g. ``"FIN"``, ``"RAP"``).
    content_types : list[str]
        Valid content type codes (e.g. ``"ORB"``, ``"CLK"``).
    format_types : list[str]
        Valid format suffix codes (e.g. ``"SP3"``, ``"BIA"``).
    formats : dict[str, Format]
        Format family definitions keyed by name.
    products : dict[str, Product]
        Product definitions keyed by name.
    """

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
    def from_yaml(cls, path: Union[str, Path] = _DEFAULT_YAML) -> "ProductSpec":
        """Load a ``ProductSpec`` from a YAML file.

        Parameters
        ----------
        path : str or Path
            Path to the YAML file.  Defaults to the bundled
            ``product_spec.yaml``.
        """
        with open(path) as fh:
            raw = yaml.safe_load(fh)
        return cls.model_validate(raw)

    # ------------------------------------------------------------------
    # Convenience look-ups
    # ------------------------------------------------------------------

    def get_format(self, name: str) -> Format:
        """Return a :class:`Format` by name, raising ``KeyError`` if absent."""
        return self.formats[name]

    def get_product(self, name: str) -> Product:
        """Return a :class:`Product` by name, raising ``KeyError`` if absent."""
        return self.products[name]

    def resolve_filename_templates(
        self,
        product_name: str,
        ref_index: int = 0,
    ) -> List[str]:
        """Return the concrete filename template(s) for a product format ref.

        Looks up the format and version, then resolves the filename
        reference (category string → templates from the parent format,
        or inline dict).

        Parameters
        ----------
        product_name : str
            Key into ``products``.
        ref_index : int
            Index into the product's ``formats`` list (default ``0``).

        Returns
        -------
        list[str]
            The resolved filename template strings.
        """
        product = self.products[product_name]
        ref = product.formats[ref_index]
        fmt = self.formats[ref.format]
        ver = fmt.versions[ref.version]

        if isinstance(ref.filename, str):
            # Reference to a category in the format version
            return ver.filename.get(ref.filename, [])
        # Inline dict override
        templates: List[str] = []
        for patterns in ref.filename.values():
            templates.extend(patterns)
        return templates

    def resolve_metadata_constraints(
        self,
        product_name: str,
        ref_index: int = 0,
    ) -> Dict[str, str]:
        """Flatten a product format ref's metadata list into a single dict.

        Parameters
        ----------
        product_name : str
            Key into ``products``.
        ref_index : int
            Index into the product's ``formats`` list.

        Returns
        -------
        dict[str, str]
            ``{field_name: constraint_pattern}`` for every constrained field.
        """
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

        Each ``{field}`` placeholder in the resolved filename template is
        replaced by:

        1. The **product-level** constraint for that field (if present).
        2. The **format-version** override (``default`` key in format
           metadata, if present).
        3. The **root** ``metadata_defaults`` regex (if present).
        4. A generic ``".+"`` catch-all.

        Literal characters in the template are escaped so the result is a
        valid Python regex.

        Parameters
        ----------
        product_name : str
            Key into ``products``.
        ref_index : int
            Index into the product's ``formats`` list.

        Returns
        -------
        list[str]
            One regex string per resolved filename template.
        """
        templates = self.resolve_filename_templates(product_name, ref_index)
        constraints = self.resolve_metadata_constraints(product_name, ref_index)

        # Format-version-level regex overrides
        product = self.products[product_name]
        ref = product.formats[ref_index]
        fmt = self.formats[ref.format]
        ver = fmt.versions[ref.version]
        format_overrides = ver.get_metadata_overrides()

        _PLACEHOLDER = re.compile(r"\{([^}]+)\}")

        # Case-insensitive lookup helper — exact match first, then
        # fall back to a case-folded comparison.
        def _ci_get(mapping: Dict[str, str], key: str) -> Optional[str]:
            if key in mapping:
                return mapping[key]
            key_lower = key.lower()
            for k, v in mapping.items():
                if k.lower() == key_lower:
                    return v
            return None

        # Word-boundary anchors (``\b``) are meaningless when a
        # pattern is substituted into a fixed placeholder position
        # inside a filename.  Strip them so adjacent literals don't
        # prevent a match.
        _WB = re.compile(r"\\b")

        def _strip_wb(pattern: str) -> str:
            return _WB.sub("", pattern)

        regexes: List[str] = []

        for tmpl in templates:
            # Split template into literal segments and placeholders
            parts: List[str] = []
            last_end = 0
            for m in _PLACEHOLDER.finditer(tmpl):
                # Escape literal text, but preserve glob-style ``.*``
                # as regex ``.*`` (match any trailing suffix or nothing)
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

            # Trailing literal (same glob→regex treatment)
            trailing = re.escape(tmpl[last_end:])
            parts.append(trailing.replace(r"\.\*", ".*").replace(r"\*", ".*"))
            regexes.append("".join(parts))

        return regexes
