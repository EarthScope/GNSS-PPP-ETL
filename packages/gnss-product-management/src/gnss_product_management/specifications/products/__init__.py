"""Author: Franklyn Dunbar"""

from .product import (
    Product as Product,
    ProductPath as ProductPath,
    VariantCatalog as VariantCatalog,
    VersionCatalog as VersionCatalog,
    infer_from_regex as infer_from_regex,
)

# ProductCatalog, ProductSpecCatalog live in catalog.py
# Import directly: from gnss_product_management.specifications.products.catalog import ProductCatalog
