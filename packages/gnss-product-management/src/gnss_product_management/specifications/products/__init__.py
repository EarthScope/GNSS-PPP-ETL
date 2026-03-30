"""Author: Franklyn Dunbar"""

from .product import (
    Product,
    ProductPath,
    VariantCatalog,
    VersionCatalog,
    infer_from_regex,
)

# ProductCatalog, ProductSpecCatalog live in catalog.py
# Import directly: from gnss_product_management.specifications.products.catalog import ProductCatalog
