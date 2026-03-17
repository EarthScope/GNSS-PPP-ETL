"""
Default singleton registries — the single place where instances are born.

Each registry is loaded from the YAML files referenced in
``gnss_ppp_products.configs`` and enriched with computed metadata
fields from ``gnss_ppp_products.utilities``.

Importing this module has side effects (file I/O + singleton creation),
which is why it lives in ``configs`` rather than ``specifications``.
"""

from __future__ import annotations

from pathlib import Path

from gnss_ppp_products.catalogs import (
    MetadataCatalog,
    ProductSpecRegistry,
    RemoteResourceFactory,
    LocalResourceFactory,
    QuerySpec,
)
from gnss_ppp_products.utilities.metadata_funcs import register_computed_fields


# ------------------------------------------------------------------
# YAML file locations (reference the originals in assets/)
# ------------------------------------------------------------------

_ASSETS_DIR = Path(__file__).resolve().parent.parent / "configs"

META_SPEC_YAML = _ASSETS_DIR / "meta" / "meta_spec.yaml"
PRODUCT_SPEC_YAML = _ASSETS_DIR / "products" / "product_spec.yaml"
LOCAL_SPEC_YAML = _ASSETS_DIR / "local" / "local_config.yaml"
QUERY_SPEC_YAML = _ASSETS_DIR / "query" / "query_config.yaml"
REMOTE_SPEC_DIR = _ASSETS_DIR / "centers"
DEPENDENCY_SPEC_DIR = _ASSETS_DIR / "tasks"

# ===================================================================
# 1. Metadata registry  (must be first — others depend on it)
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
# 3. Remote resource registry
# ===================================================================

RemoteResourceReg = RemoteResourceFactory()
for _yaml_file in sorted(REMOTE_SPEC_DIR.glob("*.yaml")):
    RemoteResourceReg.load_from_yaml(_yaml_file)
for _yml_file in sorted(REMOTE_SPEC_DIR.glob("*.yml")):
    RemoteResourceReg.load_from_yaml(_yml_file)


# ===================================================================
# 4. Local resource registry
# ===================================================================

LocalResourceReg = LocalResourceFactory()
LocalResourceReg.load_from_yaml(LOCAL_SPEC_YAML)


# ===================================================================
# 5. Query spec registry
# ===================================================================

QuerySpecReg = QuerySpec.from_yaml(QUERY_SPEC_YAML)
