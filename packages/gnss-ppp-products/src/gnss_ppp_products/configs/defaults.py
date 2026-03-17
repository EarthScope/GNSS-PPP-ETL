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

from gnss_ppp_products.catalogs import (
    MetadataCatalog,
    ProductSpecRegistry,
    LocalResourceFactory,
    RemoteResourceFactory,
    QuerySpec,
    validate_catalogs,
)
from gnss_ppp_products.utilities.metadata_funcs import register_computed_fields


# ===================================================================
# 1. Metadata catalog  (must be first — others depend on it)
# ===================================================================

MetaDataRegistry = MetadataCatalog.from_yaml(META_SPEC_YAML)
register_computed_fields(MetaDataRegistry)


# ===================================================================
# 2. Product spec registry
# ===================================================================

ProductSpecReg = ProductSpecRegistry.from_yaml(
    yaml_path=PRODUCT_SPEC_YAML,
    meta_catalog=MetaDataRegistry,
)


# ===================================================================
# 3. Remote resource factory
# ===================================================================

RemoteResourceReg = RemoteResourceFactory()
for _yaml_file in sorted(REMOTE_SPEC_DIR.glob("*.yaml")):
    RemoteResourceReg.load_from_yaml(_yaml_file)
for _yml_file in sorted(REMOTE_SPEC_DIR.glob("*.yml")):
    RemoteResourceReg.load_from_yaml(_yml_file)


# ===================================================================
# 4. Local resource factory
# ===================================================================

LocalResourceReg = LocalResourceFactory()
LocalResourceReg.load_from_yaml(LOCAL_SPEC_YAML)


# ===================================================================
# 5. Query spec
# ===================================================================

QuerySpecReg = QuerySpec.from_yaml(QUERY_SPEC_YAML)


# ===================================================================
# 6. Cross-validation
# ===================================================================

_validation_warnings = validate_catalogs(
    meta_catalog=MetaDataRegistry,
    product_registry=ProductSpecReg,
    remote_factory=RemoteResourceReg,
    local_factory=LocalResourceReg,
    query_spec=QuerySpecReg,
)
