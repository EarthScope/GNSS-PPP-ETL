"""Author: Franklyn Dunbar

Raw Pydantic models and registry for format specifications.

Two distinct types live here:

``FormatSpec`` / ``FormatVersionSpec`` / ``FormatFieldDef`` / ``FormatSpecCollection``
    Describe the *shape* of a file format as a reusable library entry — e.g.
    "RINEX v3 has these metadata fields and these filename templates".
    Loaded from the ``formats:`` section of the product spec YAML.

``FormatRegistry``
    Validates and indexes a :class:`FormatSpecCollection` against a
    :class:`ParameterCatalog`, providing ``get_format()`` / ``get_version()``
    look-ups.

See :mod:`.format_spec` for the product-facing catalog that *resolves*
format-variant bindings into :class:`~gnss_product_management.specifications.products.product.Product`
objects.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from gnss_product_management.specifications.parameters.parameter import ParameterCatalog
from pydantic import BaseModel, ConfigDict, Field, field_validator


class FormatFieldDef(BaseModel):
    """Properties of a metadata field declared inside a format version."""

    pattern: str | None = None
    default: str | None = None
    description: str | None = None


class FormatVersionSpec(BaseModel):
    """A single version of a format (e.g. RINEX v3, PRODUCT v1)."""

    model_config = ConfigDict(extra="allow")

    description: str | None = None
    notes: str | None = None
    metadata: dict[str, FormatFieldDef | None] = Field(default_factory=dict)
    file_templates: dict[str, str] = Field(default_factory=dict)
    compression: list[str] = Field(default_factory=list)

    @field_validator("file_templates", mode="before")
    @classmethod
    def _unwrap_lists(cls, v: dict) -> dict[str, str]:
        """Accept both ``str`` and ``[str]`` from YAML."""
        out: dict[str, str] = {}
        for key, val in v.items():
            if isinstance(val, list):
                out[key] = val[0] if val else ""
            else:
                out[key] = val
        return out


class FormatSpec(BaseModel):
    """A top-level format definition (e.g. RINEX, PRODUCT, TABLE).

    Contains the format description and a mapping of *version* →
    :class:`FormatVersionSpec`.  Each version in turn maps variant names
    to filename templates and metadata field definitions.

    .. note::
        This is the *format-library* model.  For the *product-facing*
        model that binds a specific format+version+variant to parameter
        lists and filename templates, see
        :class:`~gnss_product_management.specifications.format.format_spec.FormatVariantSpec`.
    """

    description: str = ""
    versions: dict[str, FormatVersionSpec] = Field(default_factory=dict)
    compression: list[str] = Field(default_factory=list)


class FormatSpecCollection(BaseModel):
    """Collection of format specifications from the ``formats:`` YAML key."""

    formats: dict[str, FormatSpec] = Field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str | Path) -> FormatSpecCollection:
        """Load from a YAML file.

        Accepts two layouts:

        1. **Wrapped** — a top-level ``formats:`` key whose value is a
           mapping of format name → :class:`FormatSpec`-compatible dict.

        2. **Flat** (``format_spec.yaml`` convention) — format names are
           top-level keys; each entry has ``versions → variants →
           {parameters, filename}`` which are converted to the
           ``metadata`` / ``file_templates`` expected by
           :class:`FormatVersionSpec`.

        Args:
            path: Path to the YAML file.

        Returns:
            A :class:`FormatSpecCollection` instance.
        """
        with open(path) as fh:
            raw = yaml.safe_load(fh)

        # Layout 1: explicit `formats:` wrapper
        if "formats" in raw:
            return cls.model_validate({"formats": raw["formats"]})

        # Layout 2: flat — convert variants/filename → metadata/file_templates
        formats: dict[str, FormatSpec] = {}
        for fmt_name, fmt_data in raw.items():
            if not isinstance(fmt_data, dict) or "versions" not in fmt_data:
                continue
            versions: dict[str, FormatVersionSpec] = {}
            for ver_name, ver_data in (fmt_data.get("versions") or {}).items():
                if not isinstance(ver_data, dict) or "variants" not in ver_data:
                    continue
                all_metadata: dict[str, FormatFieldDef | None] = {}
                file_templates: dict[str, str] = {}
                for variant_name, variant_data in (ver_data.get("variants") or {}).items():
                    if not isinstance(variant_data, dict):
                        continue
                    if filename := variant_data.get("filename"):
                        file_templates[variant_name] = filename
                    for param in variant_data.get("parameters") or []:
                        pname = param.get("name")
                        if not pname or pname in all_metadata:
                            continue
                        pattern = param.get("pattern")
                        all_metadata[pname] = FormatFieldDef(pattern=pattern) if pattern else None
                versions[str(ver_name)] = FormatVersionSpec(
                    metadata=all_metadata,
                    file_templates=file_templates,
                )
            formats[fmt_name] = FormatSpec(versions=versions)
        return cls(formats=formats)


class FormatRegistry(BaseModel):
    """Read-only registry of reusable format definitions.

    Built from a :class:`FormatSpecCollection` by resolving every metadata
    field's default value against a :class:`ParameterCatalog`.

    Attributes:
        formats: Mapping of format name to resolved :class:`FormatSpec`.
    """

    formats: dict[str, FormatSpec] = Field(default_factory=dict)

    def get_format(self, name: str) -> FormatSpec:
        """Retrieve a format by name.

        Args:
            name: Format name.

        Returns:
            The matching :class:`FormatSpec`.

        Raises:
            KeyError: If *name* is not registered.
        """
        try:
            return self.formats[name]
        except KeyError:
            raise KeyError(f"Format {name!r} not found. Available: {sorted(self.formats)}")

    def get_version(self, format_name: str, version: str) -> FormatVersionSpec:
        """Retrieve a specific version of a format.

        Args:
            format_name: Format name.
            version: Version identifier.

        Returns:
            The matching :class:`FormatVersionSpec`.

        Raises:
            KeyError: If the format or version is not found.
        """
        fmt = self.get_format(format_name)
        try:
            return fmt.versions[version]
        except KeyError:
            raise KeyError(
                f"Version {version!r} not found in format {format_name!r}. "
                f"Available: {sorted(fmt.versions)}"
            )

    @classmethod
    def build(
        cls, format_spec: FormatSpecCollection, metadata_catalog: ParameterCatalog
    ) -> FormatRegistry:
        """Build a :class:`FormatRegistry` by resolving metadata field defaults.

        Verifies that every metadata field referenced in a format version
        has either a pattern value or an entry in *metadata_catalog*.

        Args:
            format_spec: Raw format specification collection.
            metadata_catalog: Global parameter catalog for field defaults.

        Returns:
            A :class:`FormatRegistry` with all fields resolved.

        Raises:
            AssertionError: If a field is missing both a pattern and
                a catalog entry.
            ValueError: If a file template placeholder has no
                corresponding metadata field.
        """
        format_spec_collection: dict[str, FormatSpec] = format_spec.formats
        format_spec_collection_resolved: dict[str, FormatSpec] = {}

        for format_spec_name, format_spec_entry in format_spec_collection.items():
            format_version_spec_collection_resolved: dict[str, FormatVersionSpec] = {}

            for version_name, version_spec in format_spec_entry.versions.items():
                resolved_metadata = {}
                if version_spec.metadata is None:
                    continue
                for field_name, field_def in version_spec.metadata.items():
                    pattern = field_def.pattern if field_def is not None else None
                    default = field_def.default if field_def is not None else None
                    field_default = pattern or default
                    if field_default is None:
                        assert field_name in metadata_catalog.parameters, (
                            f"Field {field_name!r} not found in parameter catalog "
                            f"for format {format_spec_name!r} version {version_name!r}"
                        )
                        field_default = metadata_catalog.parameters[field_name].pattern

                    resolved_metadata[field_name] = FormatFieldDef(
                        pattern=field_default,
                        description=field_def.description if field_def is not None else None,
                    )
                for variant_name, file_template in version_spec.file_templates.items():
                    matches = re.findall(r"\{(.*?)\}", file_template)
                    for match in matches:
                        if match not in resolved_metadata:
                            raise ValueError(
                                f"Placeholder {match!r} in file template "
                                f"{file_template!r} for format {format_spec_name!r} "
                                f"version {version_name!r} variant {variant_name!r} "
                                f"does not have a corresponding metadata field."
                            )

                format_version_spec_collection_resolved[version_name] = FormatVersionSpec(
                    description=version_spec.description,
                    notes=version_spec.notes,
                    metadata=resolved_metadata,
                    file_templates=version_spec.file_templates,
                    compression=version_spec.compression,
                )
            format_spec_collection_resolved[format_spec_name] = FormatSpec(
                description=format_spec_entry.description,
                versions=format_version_spec_collection_resolved,
                compression=format_spec_entry.compression,
            )
        return FormatRegistry(formats=format_spec_collection_resolved)
