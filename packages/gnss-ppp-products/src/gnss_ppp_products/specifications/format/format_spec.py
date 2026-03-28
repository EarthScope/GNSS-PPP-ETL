"""Author: Franklyn Dunbar

Format specifications and FormatCatalog — resolves FormatSpec → Product.
"""

from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field

from gnss_ppp_products.specifications.catalog import Catalog
from gnss_ppp_products.specifications.parameters.parameter import (
    Parameter,
    ParameterCatalog,
)
from gnss_ppp_products.specifications.products.product import (
    Product,
    ProductPath,
    VariantCatalog,
    VersionCatalog,
)


class FormatSpec(BaseModel):
    """A single file-format definition with parameter overrides and filename template."""

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
            filename=ProductPath(pattern=self.filename) if self.filename else None,
        )


class FormatSpecCatalog(BaseModel):
    """Collection of raw format specifications loaded from YAML."""

    formats: dict[str, VersionCatalog[FormatSpec]]

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
    """Resolved format catalog — maps format names to VersionCatalog[VariantCatalog[Product]]."""

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
        return cls(formats=formats)

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
        return FormatCatalog(formats=merged)
