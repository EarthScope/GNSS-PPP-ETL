"""
Default singleton registries — the single place where instances are born.

Each registry is loaded from the YAML files referenced in
``gnss_ppp_products.configs`` and enriched with computed metadata
fields from ``gnss_ppp_products.utilities``.

Importing this module has side effects (file I/O + singleton creation),
which is why it lives in ``configs`` rather than ``specifications``.
"""

from __future__ import annotations

from . import (
    META_SPEC_YAML,
    PRODUCT_SPEC_YAML,
    LOCAL_SPEC_YAML,
    QUERY_SPEC_YAML,
    REMOTE_SPEC_DIR,
)

from gnss_ppp_products.specifications.metadata import _MetadataRegistry
from gnss_ppp_products.specifications.products import _ProductSpecRegistry
from gnss_ppp_products.specifications.remote import _RemoteResourceRegistry
from gnss_ppp_products.specifications.local import _LocalResourceRegistry
from gnss_ppp_products.specifications.query.models import QuerySpec

from gnss_ppp_products.utilities.metadata_funcs import register_computed_fields


# ===================================================================
# 1. Metadata registry  (must be first — others depend on it)
# ===================================================================

MetaDataRegistry = _MetadataRegistry.from_yaml(META_SPEC_YAML)
register_computed_fields(MetaDataRegistry)


# ===================================================================
# 2. Product spec registry
# ===================================================================

ProductSpecRegistry = _ProductSpecRegistry.load_from_yaml(
    yaml_path=PRODUCT_SPEC_YAML,
    meta_registry=MetaDataRegistry,
)


# ===================================================================
# 3. Remote resource registry
# ===================================================================

RemoteResourceRegistry = _RemoteResourceRegistry.load_from_directory(REMOTE_SPEC_DIR)


# ===================================================================
# 4. Local resource registry
# ===================================================================

LocalResourceRegistry = _LocalResourceRegistry.load_from_yaml(LOCAL_SPEC_YAML)


# ===================================================================
# 5. Query spec registry
# ===================================================================

QuerySpecRegistry = QuerySpec.from_yaml(QUERY_SPEC_YAML)
