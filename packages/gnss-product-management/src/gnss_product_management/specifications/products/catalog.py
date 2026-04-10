"""Author: Franklyn Dunbar

ProductSpec and ProductCatalog — resolve product specs against FormatCatalog.
"""

import re

from gnss_product_management.specifications.catalog import Catalog
from gnss_product_management.specifications.format.format_spec import FormatCatalog
from gnss_product_management.specifications.parameters.parameter import Parameter
from gnss_product_management.specifications.products.product import (
    PathTemplate,
    Product,
    VariantCatalog,
    VersionCatalog,
)
from pydantic import BaseModel, Field


class ProductSpec(BaseModel):
    """A product specification that binds to a format variant with parameter overrides."""

    name: str
    format: str
    version: str
    variant: str
    parameters: list[Parameter] | None = Field(default_factory=list)
    filename: str | None = Field(
        default=None,
        description="Product-level filename override (takes precedence over format filename).",
    )

    def materialize(self, format_catalog: FormatCatalog) -> Product:
        """Materialize against a FormatCatalog to produce a fully-merged Product.

        Args:
            format_catalog: Resolved format catalog.

        Returns:
            A :class:`Product` with format-level parameters overlaid by
            product-spec overrides.
        """
        format_spec: Product = (
            format_catalog.formats[self.format].versions[self.version].variants[self.variant]
        )

        # Start with ALL format parameters, then overlay product spec overrides
        resolved_parameters = {p.name: p.model_copy(deep=True) for p in format_spec.parameters}
        for param in self.parameters:
            if param.name in resolved_parameters:
                resolved_parameters[param.name] = resolved_parameters[param.name].model_copy(
                    update=param.model_dump(exclude_none=True), deep=True
                )
            else:
                resolved_parameters[param.name] = param

        update = {"name": self.name, "parameters": list(resolved_parameters.values())}
        # Product-level filename overrides the format filename
        if self.filename:
            update["filename"] = PathTemplate(pattern=self.filename)

        return format_spec.model_copy(
            update=update,
            deep=True,
        )


class ProductSpecCatalog(BaseModel):
    """Collection of raw product specifications loaded from YAML.

    Attributes:
        products: Mapping of product name to version/variant spec hierarchy.
    """

    products: dict[str, VersionCatalog[ProductSpec]]

    @classmethod
    def from_yaml(cls, path) -> "ProductSpecCatalog":
        """Load product specs from a YAML file, extracting the ``products:`` section.

        Transforms the YAML structure into nested Pydantic models by injecting
        ``name`` from dict keys and converting ``formats`` lists into version/variant dicts.
        """
        import yaml

        with open(path) as f:
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
        """Merge another catalog into this one.

        Duplicate entries are overwritten by *other* with a warning.

        Args:
            other: Catalog to merge.

        Returns:
            A new :class:`ProductSpecCatalog` with combined entries.
        """
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
                        merged[name].versions[version_name] = VariantCatalog(variants={})
                    merged[name].versions[version_name].variants[variant_name] = prod
        return ProductSpecCatalog(products={k: v.model_dump() for k, v in merged.items()})


class ProductCatalog(Catalog):
    """Resolved product catalog — maps product names to VersionCatalog[VariantCatalog[Product]].

    Attributes:
        products: Mapping of product name to version/variant product hierarchy.
    """

    products: dict[str, VersionCatalog[Product]]

    @classmethod
    def build(
        cls, product_spec_catalog: ProductSpecCatalog, format_catalog: FormatCatalog
    ) -> "ProductCatalog":
        """Build concrete Products from abstract product specs and a FormatCatalog.

        Args:
            product_spec_catalog: Raw product spec definitions.
            format_catalog: Resolved format catalog.

        Returns:
            A :class:`ProductCatalog` with all products materialized.
        """
        products = {}

        for product_name, product_spec_cat in product_spec_catalog.products.items():
            versions = {}
            for version_name, version_spec in product_spec_cat.versions.items():
                variants = {}
                for variant_name, product_spec in version_spec.variants.items():
                    product: Product = product_spec.materialize(format_catalog)
                    if hasattr(product, "filename") and hasattr(product.filename, "derive"):
                        product.filename.derive(product.parameters)
                    variants[variant_name] = product
                versions[version_name] = VariantCatalog(variants=variants)
            products[product_name] = VersionCatalog(versions=versions)

        return cls(products={k: v.model_dump() for k, v in products.items()})

    def merge(self, other: "ProductCatalog") -> "ProductCatalog":
        """Merge another catalog into this one.

        Duplicate entries are overwritten by *other* with a warning.

        Args:
            other: Catalog to merge.

        Returns:
            A new :class:`ProductCatalog` with combined entries.
        """
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
                        merged[name].versions[version_name] = VariantCatalog(variants={})
                    merged[name].versions[version_name].variants[variant_name] = prod
        return ProductCatalog(products={k: v.model_dump() for k, v in merged.items()})
