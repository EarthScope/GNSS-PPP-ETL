"""Author: Franklyn Dunbar"""

from .spec import FormatFieldDef, FormatVersionSpec, FormatSpec, FormatSpecCollection

# FormatCatalog, FormatSpecCatalog live in format_spec.py
# Import directly: from gnss_product_management.specifications.format.format_spec import FormatCatalog

# FormatRegistry lives in format_catalog.py (read-only registry of raw format specs)
# Import directly: from gnss_product_management.specifications.format.format_catalog import FormatRegistry
