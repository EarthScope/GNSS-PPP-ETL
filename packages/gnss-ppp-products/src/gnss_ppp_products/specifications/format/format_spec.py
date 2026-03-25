"""Format specifications and FormatCatalog — resolves FormatSpec → Product."""

import re
from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field

from gnss_ppp_products.specifications.catalog import Catalog
from gnss_ppp_products.specifications.parameters.parameter import Parameter, ParameterCatalog
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
        """Materialize against a ParameterCatalog to produce a Product."""
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
    formats: dict[str, VersionCatalog[FormatSpec]]

    @classmethod
    def from_yaml(cls, path: Path) -> "FormatSpecCatalog":
        """Load from a YAML file, transforming the nested format structure.

        Reads the ``formats:`` section and for each format/version/variant
        injects ``name`` from the dict keys and converts ``file_templates``
        entries into ``FormatSpec`` variant dicts.
        """
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        result = {}
        for fmt_name, fmt_data in data.items():
            versions = {}
            for ver_name, ver_data in (fmt_data.get("versions") or {}).items():
                metadata = ver_data.get("metadata") or {}
                parameters = []
                for param_name, param_data in metadata.items():
                    p: dict = {"name": param_name}
                    if param_data and isinstance(param_data, dict):
                        if "default" in param_data and "pattern" not in param_data:
                            param_data = {**param_data, "pattern": param_data.pop("default")}
                        p.update(param_data)
                    parameters.append(p)
                variant_data = ver_data.get("variants") or {}
                variants = {}
                for variant_name, variant in variant_data.items():
                    filename = variant.get("filename")
                    variant_param_names = set(re.findall(r"\{(\w+)\}", filename))
                    variant_params = [p for p in parameters if p["name"] in variant_param_names]
                    variants[variant_name] = {
                        "name": fmt_name,
                        "version": str(ver_name),
                        "variant": variant_name,
                        "parameters": variant_params,
                        "filename": filename,
                    }
                versions[str(ver_name)] = {"variants": variants}
            result[fmt_name] = {"versions": versions}
        assert result, f"No formats found in {path}"
        return cls(formats=result)


class FormatCatalog(Catalog):
    """Resolved format catalog — maps format names to VersionCatalog[VariantCatalog[Product]]."""
    formats: dict[str, VersionCatalog[Product]]

    @classmethod
    def build(cls, format_spec_catalog: FormatSpecCatalog, parameter_catalog: ParameterCatalog) -> "FormatCatalog":
        """Build concrete Products from abstract format specs and a ParameterCatalog."""
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
        """Merge another catalog into this one. Raise a warning if there are duplicate format names."""
        merged = self.formats.copy()
        for name, version_cat in other.formats.items():
            for version_name, variant_cat in version_cat.versions.items():
                for variant_name, product in variant_cat.variants.items():
                    if (
                        merged
                        .get(name, VersionCatalog(versions={}))
                        .versions.get(version_name, VariantCatalog(variants={}))
                        .variants.get(variant_name)
                        ):
                        print(f"Warning: Duplicate format {name!r} version {version_name!r} variant {variant_name!r} found. Overwriting with new value.")
                    if name not in merged:
                        merged[name] = VersionCatalog(versions={})
                    if version_name not in merged[name].versions:
                        merged[name].versions[version_name] = VariantCatalog(variants={})
                    merged[name].versions[version_name].variants[variant_name] = product
        return FormatCatalog(formats=merged)