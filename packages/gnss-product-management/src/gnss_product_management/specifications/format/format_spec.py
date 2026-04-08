"""Author: Franklyn Dunbar

Format-variant specifications and FormatCatalog — resolves FormatVariantSpec → Product.
"""

from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field

from gnss_product_management.specifications.catalog import Catalog
from gnss_product_management.specifications.parameters.parameter import (
    Parameter,
    ParameterCatalog,
)
from gnss_product_management.specifications.products.product import (
    Product,
    PathTemplate,
    VariantCatalog,
    VersionCatalog,
)


class FormatVariantSpec(BaseModel):
    """A single file-format variant binding: name × version × variant → parameters + filename.

    This is a resolved "leaf" entry in the format spec YAML — it names
    which format (e.g. ``RINEX``), which version (``"3"``), which variant
    (``observation``), and lists the parameters and filename template that
    together define a concrete file shape.
    """

    name: str
    version: Optional[str] = None
    variant: Optional[str] = None
    parameters: Optional[List[dict]] = Field(default_factory=list)
    filename: Optional[str] = None

    def materialize(self, parameter_catalog: ParameterCatalog) -> Product:
        """Materialize against a ParameterCatalog to produce a Product.

        Args:
            parameter_catalog: Global parameter catalog for defaults.

        Returns:
            A :class:`Product` with resolved parameters.
        """
        resolved_parameters = {}
        for param in self.parameters:
            name = param["name"]
            default = parameter_catalog.get(name, None)
            if default is not None:
                resolved_param = default.model_copy(update=param, deep=True)
            else:
                resolved_param = Parameter(**param)
            resolved_parameters[name] = resolved_param

        return Product(
            name=self.name,
            parameters=list(resolved_parameters.values()),
            filename=PathTemplate(pattern=self.filename) if self.filename else None,
        )


class FormatSpecCatalog(BaseModel):
    """Collection of raw format-variant specifications loaded from YAML."""

    formats: dict[str, VersionCatalog[FormatVariantSpec]]

    @classmethod
    def from_yaml(cls, path: Path) -> "FormatSpecCatalog":
        """Load from a YAML file containing pre-built format specs.

        Expected YAML layout::

            FORMAT_NAME:
              name: FORMAT_NAME
              versions:
                "1":
                  name: "1"
                  variants:
                    variant_name:
                      name: FORMAT_NAME
                      version: "1"
                      variant: variant_name
                      parameters:
                        - name: PARAM
                      filename: "{PARAM}..."
        """
        with open(path, "r") as f:
            data = yaml.safe_load(f)

        result = {}
        for fmt_name, fmt_data in data.items():
            if not isinstance(fmt_data, dict) or "versions" not in fmt_data:
                continue
            versions = {}
            for ver_name, ver_data in (fmt_data.get("versions") or {}).items():
                if not isinstance(ver_data, dict) or "variants" not in ver_data:
                    continue
                variants = {}
                for variant_name, variant in (ver_data.get("variants") or {}).items():
                    variants[variant_name] = variant
                versions[str(ver_name)] = {"variants": variants}
            result[fmt_name] = {"versions": versions}
        assert result, f"No formats found in {path}"
        return cls(formats=result)


class FormatCatalog(Catalog):
    """Resolved format catalog — maps format names to VersionCatalog[VariantCatalog[Product]].

    Attributes:
        formats: Mapping of format name to version/variant product hierarchy.
    """

    formats: dict[str, VersionCatalog[Product]]

    @classmethod
    def build(
        cls, format_spec_catalog: FormatSpecCatalog, parameter_catalog: ParameterCatalog
    ) -> "FormatCatalog":
        """Build concrete Products from abstract format specs and a ParameterCatalog.

        Args:
            format_spec_catalog: The raw format spec definitions.
            parameter_catalog: Global parameter catalog.

        Returns:
            A :class:`FormatCatalog` mapping format names to resolved products.
        """
        formats = {}
        for format_name, format_spec_cat in format_spec_catalog.formats.items():
            versions = {}
            for version_name, version_spec in format_spec_cat.versions.items():
                variants = {}
                for variant_name, format_spec in version_spec.variants.items():
                    product = format_spec.materialize(parameter_catalog)
                    variants[variant_name] = product
                versions[version_name] = VariantCatalog(variants=variants)
            formats[format_name] = VersionCatalog(versions=versions)
        return cls(formats={k: v.model_dump() for k, v in formats.items()})

    def merge(self, other: "FormatCatalog") -> "FormatCatalog":
        """Merge another catalog into this one.

        Duplicate entries are overwritten by *other* with a warning.

        Args:
            other: Catalog to merge.

        Returns:
            A new :class:`FormatCatalog` with combined entries.
        """
        merged = self.formats.copy()
        for name, version_cat in other.formats.items():
            for version_name, variant_cat in version_cat.versions.items():
                for variant_name, product in variant_cat.variants.items():
                    if (
                        merged.get(name, VersionCatalog(versions={}))
                        .versions.get(version_name, VariantCatalog(variants={}))
                        .variants.get(variant_name)
                    ):
                        print(
                            f"Warning: Duplicate format {name!r} version {version_name!r} variant {variant_name!r} found. Overwriting with new value."
                        )
                    if name not in merged:
                        merged[name] = VersionCatalog(versions={})
                    if version_name not in merged[name].versions:
                        merged[name].versions[version_name] = VariantCatalog(
                            variants={}
                        )
                    merged[name].versions[version_name].variants[variant_name] = product
        return FormatCatalog(formats={k: v.model_dump() for k, v in merged.items()})
