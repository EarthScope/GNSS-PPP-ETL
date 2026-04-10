"""Author: Franklyn Dunbar"""

from .product import (
    PathTemplate as PathTemplate,
)
from .product import (
    Product as Product,
)
from .product import (
    VariantCatalog as VariantCatalog,
)
from .product import (
    VersionCatalog as VersionCatalog,
)
from .product import (
    infer_from_regex as infer_from_regex,
)

# ProductCatalog, ProductSpecCatalog live in catalog.py
# Import directly: from gnss_product_management.specifications.products.catalog import ProductCatalog
