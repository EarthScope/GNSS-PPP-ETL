"""Format specifications and FormatCatalog — resolves FormatSpec → Product."""

from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field

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

    def resolve(self, parameter_catalog: ParameterCatalog) -> Product:
        """Resolve against a ParameterCatalog to produce a Product."""
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


class FormatSpecVariantCatalog(BaseModel):
    name: str
    variants: dict[str, FormatSpec]


class FormatSpecVersionCatalog(BaseModel):
    name: str
    versions: dict[str, FormatSpecVariantCatalog]


class FormatSpecCatalog(BaseModel):
    formats: dict[str, FormatSpecVersionCatalog]

    @classmethod
    def from_yaml(cls, path: Path) -> "FormatSpecCatalog":
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return cls(**data.get("formats", {}))


class FormatCatalog(BaseModel):
    """Resolved format catalog — maps format names to VersionCatalog[VariantCatalog[Product]]."""
    formats: dict[str, VersionCatalog]

    def __init__(self, format_spec_catalog: FormatSpecCatalog, parameter_catalog: ParameterCatalog):
        formats = {}
        for format_name, format_spec_cat in format_spec_catalog.formats.items():
            versions = {}
            for version_name, version_spec in format_spec_cat.versions.items():
                variants = {}
                for variant_name, format_spec in version_spec.variants.items():
                    product = format_spec.resolve(parameter_catalog)
                    variants[variant_name] = product
                versions[version_name] = VariantCatalog(name=version_spec.name, variants=variants)
            formats[format_name] = VersionCatalog(name=format_spec_cat.name, versions=versions)
        super().__init__(formats=formats)
