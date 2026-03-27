"""ProductSpec and ProductCatalog — resolve product specs against FormatCatalog."""

import re
from typing import List, Optional

from pydantic import BaseModel, Field

from gnss_ppp_products.specifications.catalog import Catalog
from gnss_ppp_products.specifications.parameters.parameter import Parameter
from gnss_ppp_products.specifications.products.product import (
    Product,
    ProductPath,
    VariantCatalog,
    VersionCatalog,
)
from gnss_ppp_products.specifications.format.format_spec import FormatCatalog


class ProductSpec(BaseModel):
    """A product specification that binds to a format variant with parameter overrides."""

    name: str
    format: str
    version: str
    variant: str
    parameters: Optional[List[Parameter]] = Field(default_factory=list)
    filename: Optional[str] = Field(
        default=None,
        description="Product-level filename override (takes precedence over format filename).",
    )

    def materialize(self, format_catalog: FormatCatalog) -> Product:
        """Materialize against a FormatCatalog to produce a fully-merged Product."""
        format_spec: Product = (
            format_catalog.formats[self.format]
            .versions[self.version]
            .variants[self.variant]
        )

        # Start with ALL format parameters, then overlay product spec overrides
        resolved_parameters = {
            p.name: p.model_copy(deep=True) for p in format_spec.parameters
        }
        for param in self.parameters:
            if param.name in resolved_parameters:
                resolved_parameters[param.name] = resolved_parameters[
                    param.name
                ].model_copy(update=param.model_dump(exclude_none=True), deep=True)
            else:
                resolved_parameters[param.name] = param

        update = {"name": self.name, "parameters": list(resolved_parameters.values())}
        # Product-level filename overrides the format filename
        if self.filename:
            update["filename"] = ProductPath(pattern=self.filename)

        return format_spec.model_copy(
            update=update,
            deep=True,
        )


class ProductSpecCatalog(BaseModel):
    products: dict[str, VersionCatalog[ProductSpec]]

    @classmethod
    def from_yaml(cls, path) -> "ProductSpecCatalog":
        """Load product specs from a YAML file, extracting the ``products:`` section.

        Transforms the YAML structure into nested Pydantic models by injecting
        ``name`` from dict keys and converting ``formats`` lists into version/variant dicts.
        """
        import yaml
        from pathlib import Path

        with open(path, "r") as f:
            data = yaml.safe_load(f)
        result = {}
        for prod_name, prod_data in data.get("products", {}).items():
            versions: dict = {}
            for fmt_entry in prod_data.get("formats", []):
                version = str(fmt_entry.get("version", "1"))
                variant = fmt_entry.get("variant", "default")
                format_name = fmt_entry["format"]
                parameters = []
                for c_name, c_value in (fmt_entry.get("constraints") or {}).items():
                    if re.search(r"[\[\]\\(){}|*+?^$]", str(c_value)):
                        parameters.append({"name": c_name, "pattern": c_value})
                    else:
                        parameters.append({"name": c_name, "value": c_value})
                variant_dict: dict = {
                    "name": prod_name,
                    "format": format_name,
                    "version": version,
                    "variant": variant,
                    "parameters": parameters,
                }
                templates = fmt_entry.get("file_templates")
                if templates:
                    variant_dict["filename"] = templates[0]
                if version not in versions:
                    versions[version] = {"variants": {}}
                versions[version]["variants"][variant] = variant_dict
            result[prod_name] = {"versions": versions}
        return cls(products=result)

    def merge(self, other: "ProductSpecCatalog") -> "ProductSpecCatalog":
        """Merge another catalog into this one. Raise a warning if there are duplicate product names."""
        merged = self.products.copy()
        for name, product in other.products.items():
            for version_name, variant_cat in product.versions.items():
                for variant_name, prod in variant_cat.variants.items():
                    if (
                        merged.get(name, VersionCatalog(versions={}))
                        .versions.get(version_name, VariantCatalog(variants={}))
                        .variants.get(variant_name)
                    ):
                        print(
                            f"Warning: Duplicate product spec {name!r} version {version_name!r} variant {variant_name!r} found. Overwriting with new value."
                        )
                    if name not in merged:
                        merged[name] = VersionCatalog(versions={})
                    if version_name not in merged[name].versions:
                        merged[name].versions[version_name] = VariantCatalog(
                            variants={}
                        )
                    merged[name].versions[version_name].variants[variant_name] = prod
        return ProductSpecCatalog(products=merged)


class ProductCatalog(Catalog):
    """Resolved product catalog — maps product names to VersionCatalog[VariantCatalog[Product]]."""

    products: dict[str, VersionCatalog[Product]]

    @classmethod
    def build(
        cls, product_spec_catalog: ProductSpecCatalog, format_catalog: FormatCatalog
    ) -> "ProductCatalog":
        """Build concrete Products from abstract product specs and a FormatCatalog."""
        products = {}

        for product_name, product_spec_cat in product_spec_catalog.products.items():
            versions = {}
            for version_name, version_spec in product_spec_cat.versions.items():
                variants = {}
                for variant_name, product_spec in version_spec.variants.items():
                    product: Product = product_spec.materialize(format_catalog)
                    if hasattr(product, "filename") and hasattr(
                        product.filename, "derive"
                    ):
                        product.filename.derive(product.parameters)
                    variants[variant_name] = product
                versions[version_name] = VariantCatalog(variants=variants)
            products[product_name] = VersionCatalog(versions=versions)

        return cls(products=products)

    def merge(self, other: "ProductCatalog") -> "ProductCatalog":
        """Merge another catalog into this one. Raise a warning if there are duplicate product names."""
        merged = self.products.copy()
        for name, product in other.products.items():
            for version_name, variant_cat in product.versions.items():
                for variant_name, prod in variant_cat.variants.items():
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
                    merged[name].versions[version_name].variants[variant_name] = prod
        return ProductCatalog(products=merged)
