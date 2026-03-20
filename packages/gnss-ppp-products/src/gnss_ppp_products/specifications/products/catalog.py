"""ProductSpec and ProductCatalog — resolve product specs against FormatCatalog."""

from typing import List, Optional

from pydantic import BaseModel, Field

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
    filename: Optional[str] = Field(default=None, description="Product-level filename override (takes precedence over format filename).")

    def resolve(self, format_catalog: FormatCatalog) -> Product:
        """Resolve against a FormatCatalog to produce a fully-merged Product."""
        format_spec: Product = format_catalog.formats[self.format].versions[self.version].variants[self.variant]

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
            update["filename"] = ProductPath(pattern=self.filename)

        return format_spec.model_copy(
            update=update,
            deep=True,
        )


class ProductSpecVariantCatalog(BaseModel):
    name: str
    variants: dict[str, ProductSpec]


class ProductSpecVersionCatalog(BaseModel):
    name: str
    versions: dict[str, ProductSpecVariantCatalog]


class ProductSpecCatalog(BaseModel):
    products: dict[str, ProductSpecVersionCatalog]


class ProductCatalog(BaseModel):
    """Resolved product catalog — maps product names to VersionCatalog[VariantCatalog[Product]]."""
    products: dict[str, VersionCatalog]

    def __init__(self, product_spec_catalog: ProductSpecCatalog, format_catalog: FormatCatalog):
        products = {}

        for product_name, product_spec_cat in product_spec_catalog.products.items():
            versions = {}
            for version_name, version_spec in product_spec_cat.versions.items():
                variants = {}
                for variant_name, product_spec in version_spec.variants.items():
                    product: Product = product_spec.resolve(format_catalog)
                    if hasattr(product, "filename") and hasattr(product.filename, "derive"):
                        product.filename.derive(product.parameters)
                    variants[variant_name] = product
                versions[version_name] = VariantCatalog(name=version_spec.name, variants=variants)
            products[product_name] = VersionCatalog(name=product_spec_cat.name, versions=versions)

        super().__init__(products=products)
