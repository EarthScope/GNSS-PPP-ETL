from pathlib import Path
from typing import Dict, List, Optional

from gnss_ppp_products.specifications.metadata import MetadataCatalog,MetadataSpec
from gnss_ppp_products.specifications.products import ProductCatalog,ProductSpecCollection, ProductVariant
from gnss_ppp_products.specifications.remote import RemoteResourceFactory,RemoteResourceSpec, RemoteResourceCatalog
from gnss_ppp_products.specifications.format import FormatCatalog,FormatSpecCollection
from gnss_ppp_products.specifications.local import LocalResourceSpec, LocalResourceFactory

config_dir = Path(__file__).parent.parent / "src" / "gnss_ppp_products" / "configs"

meta_config_path = config_dir / "meta"/"meta_spec.yaml"
metadata_spec: MetadataCatalog = MetadataCatalog.from_yaml(meta_config_path)

format_spec_path = config_dir / "products" / "product_spec.yaml"
format_spec: FormatSpecCollection = FormatSpecCollection.from_yaml(format_spec_path)
format_catalog = FormatCatalog.resolve(format_spec,metadata_spec)

product_config_path = config_dir / "products"/"product_spec.yaml"
product_spec: ProductSpecCollection = ProductSpecCollection.from_yaml(product_config_path)
product_catalog = ProductCatalog.resolve(product_spec_collection=product_spec, format_catalog=format_catalog)

local_resource_config_path = config_dir / "local" / "local_config.yaml"
local_resource_spec: LocalResourceSpec = LocalResourceSpec.from_yaml(local_resource_config_path)
local_resource_factory = LocalResourceFactory.resolve(local_resource_spec, product_catalog)

remote_resource_config_paths = (config_dir/"centers").glob("*.yaml")
remote_resource_specs = [RemoteResourceSpec.from_yaml(p) for p in remote_resource_config_paths]
remote_resource_catalogs = [RemoteResourceCatalog.resolve(spec, product_catalog, metadata_spec) for spec in remote_resource_specs]
remote_resource_factory = RemoteResourceFactory(product_catalog, metadata_spec)
for catalog in remote_resource_catalogs:
    remote_resource_factory._register(catalog)