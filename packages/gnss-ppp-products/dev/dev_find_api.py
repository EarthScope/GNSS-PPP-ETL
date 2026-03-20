'''
Lazy narrowing query factory for GNSS product discovery.

Integration test script — imports from src/gnss_ppp_products modules.
Seed data still loaded from dev_specs.py for now.
'''

import asyncio
import datetime
import logging
from pathlib import Path

from gnss_ppp_products.specifications.local.local import LocalResourceSpec
from gnss_ppp_products.utilities.metadata_funcs import register_computed_fields

from gnss_ppp_products.specifications.parameters.parameter import Parameter, ParameterCatalog
from gnss_ppp_products.specifications.products.product import Product, ProductPath, VariantCatalog, VersionCatalog
from gnss_ppp_products.specifications.products.catalog import ProductCatalog, ProductSpecCatalog
from gnss_ppp_products.specifications.format.format_spec import FormatCatalog, FormatSpecCatalog
from gnss_ppp_products.specifications.remote.resource import (
    ResourceProductSpec,
    ResourceSpec,
    ResourceQuery,
    Server,
)
from gnss_ppp_products.specifications.local.factory import LocalResourceFactory as LocalResourceFactory
from gnss_ppp_products.factories.remote_factory import RemoteResourceFactory
from gnss_ppp_products.factories.query_factory import QueryFactory, QueryProfile
from gnss_ppp_products.factories.resource_fetcher import ResourceFetcher, FetchResult
from gnss_ppp_products.utilities.helpers import _listify, expand_dict_combinations

import sys
sys.path.append(str(Path(__file__).parent))
from dev_specs import (
    parameter_spec_dict,
    format_spec_dict,
    product_spec_dict,
    wuhan_resource_spec_dict,
    igs_resource_spec_dict,
    code_resource_spec_dict,
    local_resource_spec_dict,
)

logger = logging.getLogger(__name__)


LOCAL_CONFIG_PATH = Path(__file__).resolve().parent.parent / "src" / "gnss_ppp_products" / "configs" / "local" / "local_config.yaml"


if __name__ == "__main__":
    from pathlib import Path
    date = datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc)
    base_dir = Path("/Volumes/DunbarSSD/Project/SeafloorGeodesy/GNSS-PPP")
    PARAMETER_CATALOG = ParameterCatalog(parameters=[Parameter(**p) for p in parameter_spec_dict])
    register_computed_fields(PARAMETER_CATALOG)
    FORMAT_CATALOG = FormatCatalog(
        format_spec_catalog=FormatSpecCatalog(formats=format_spec_dict),
        parameter_catalog=PARAMETER_CATALOG,
    )
    PRODUCT_CATALOG = ProductCatalog(
        product_spec_catalog=ProductSpecCatalog(products=product_spec_dict),
        format_catalog=FORMAT_CATALOG,
    )
    REMOTE_RESOURCE_FACTORY = RemoteResourceFactory(PRODUCT_CATALOG)
    REMOTE_RESOURCE_FACTORY.register(ResourceSpec(**wuhan_resource_spec_dict))
    REMOTE_RESOURCE_FACTORY.register(ResourceSpec(**igs_resource_spec_dict))
    REMOTE_RESOURCE_FACTORY.register(ResourceSpec(**code_resource_spec_dict))
    LOCAL_SPEC = LocalResourceSpec.from_yaml(str(LOCAL_CONFIG_PATH))
    local = LocalResourceFactory(LOCAL_SPEC, PRODUCT_CATALOG, PARAMETER_CATALOG, base_dir=base_dir)

    QF = QueryFactory(
        remote_factory=REMOTE_RESOURCE_FACTORY,
        local_factory=local,
        product_catalog=PRODUCT_CATALOG,
        parameter_catalog=PARAMETER_CATALOG,
    )

    test = QF.get(
        date=date,
        product={"name": "ORBIT", "version": ["1"]},
        parameters={"AAA": ["WUM","WMC"]},
    )

    # ── ResourceFetcher demo ─────────────────────────────────────
    print("\n" + "=" * 60)
    print("ResourceFetcher — searching for files…")
    print("=" * 60)
    fetcher = ResourceFetcher()
    fetch_results = fetcher.search(test)
    for fr in fetch_results:
        status = "FOUND" if fr.found else ("ERROR" if fr.error else "NO MATCH")
        dir_str = ResourceFetcher._get_directory(fr.query) or "?"
        print(f"\n[{status}] {fr.query.server.hostname} | {dir_str}")
        print(f"  Pattern:  {ResourceFetcher._get_file_pattern(fr.query)}")
        if fr.found:
            print(f"  Matches:  {fr.matched_filenames[:5]}")
            print(f"  dir.value = {fr.query.directory.value if isinstance(fr.query.directory, ProductPath) else fr.query.directory}")
            print(f"  fn.value  = {fr.query.product.filename.value if fr.query.product.filename else None}")
        elif fr.error:
            print(f"  Error:    {fr.error}")
    
    found = [fr for fr in fetch_results if fr.found]

    # ── Download found products ──────────────────────────────────
    if found:
        print(f"\nDownloading {sum(len(fr.matched_filenames) for fr in found)} file(s) from {len(found)} source(s)…")
        asyncio.run(fetcher.download(fetch_results, local, date))
        for fr in found:
            if fr.downloaded:
                print(f"  ✓ {fr.query.server.hostname} → {fr.download_dest}")
            else:
                print(f"  ✗ {fr.query.server.hostname} — download failed")
    else:
        print("\nNo remote files found to download.")
