"""Author: Franklyn Dunbar

Format registry — loads and indexes raw format specifications from YAML.
"""

from __future__ import annotations

import re
from typing import Dict

from pydantic import BaseModel, Field

from gnss_product_management.specifications.format.spec import (
    FormatFieldDef,
    FormatSpec,
    FormatVersionSpec,
    FormatSpecCollection,
)
from gnss_product_management.specifications.parameters.parameter import ParameterCatalog


class FormatRegistry(BaseModel):
    """Read-only registry of reusable format definitions.

    Loaded from the ``formats:`` key of the product spec YAML.

    Attributes:
        formats: Mapping of format name to :class:`FormatSpec`.
    """

    formats: Dict[str, FormatSpec] = Field(default_factory=dict)

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
            raise KeyError(
                f"Format {name!r} not found. Available: {sorted(self.formats)}"
            )

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
        """Build a FormatRegistry by resolving metadata field defaults.

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
        format_spec_collection: Dict[str, FormatSpec] = format_spec.formats
        format_spec_collection_resolved: Dict[str, FormatSpec] = {}

        for format_spec_name, format_spec_entry in format_spec_collection.items():
            format_version_spec_collection_resolved: Dict[str, FormatVersionSpec] = {}

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
                            f"Field {field_name!r} not found in parameter catalog for format {format_spec_name!r} version {version_name!r}"
                        )
                        field_default = metadata_catalog.parameters[field_name].pattern

                    resolved_metadata[field_name] = FormatFieldDef(
                        pattern=field_default,
                        description=field_def.description
                        if field_def is not None
                        else None,
                    )
                for variant_name, file_template in version_spec.file_templates.items():
                    # Check if all placeholders in the file template have corresponding metadata fields
                    # get all strings within curly braces in file_template

                    matches = re.findall(r"\{(.*?)\}", file_template)
                    for match in matches:
                        if match not in resolved_metadata:
                            raise ValueError(
                                f"Placeholder {match!r} in file template {file_template!r} for format {format_spec_name!r} version {version_name!r} variant {variant_name!r} does not have a corresponding metadata field."
                            )

                format_version_spec_collection_resolved[version_name] = (
                    FormatVersionSpec(
                        description=version_spec.description,
                        notes=version_spec.notes,
                        metadata=resolved_metadata,
                        file_templates=version_spec.file_templates,
                        compression=version_spec.compression,
                    )
                )
            format_spec_collection_resolved[format_spec_name] = FormatSpec(
                description=format_spec_entry.description,
                versions=format_version_spec_collection_resolved,
                compression=format_spec_entry.compression,
            )
        return FormatRegistry(formats=format_spec_collection_resolved)
