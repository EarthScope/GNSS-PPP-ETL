'''
Lazy narrowing query factory for GNSS product discovery.

Integration test script — imports from src/gnss_ppp_products modules.
Seed data still loaded from dev_specs.py for now.
'''

import asyncio
import datetime
import logging
from pathlib import Path

from gnss_ppp_products.specifications.products.product import ProductPath
from gnss_ppp_products.factories import ProductEnvironment, QueryFactory, ResourceFetcher, FetchResult

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
    date = datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc)

    env = ProductEnvironment(
        base_dir="/Volumes/DunbarSSD/Project/SeafloorGeodesy/GNSS-PPP",
        parameter_specs=parameter_spec_dict,
        format_specs=format_spec_dict,
        product_specs=product_spec_dict,
        local_config=LOCAL_CONFIG_PATH,
        remote_specs=[wuhan_resource_spec_dict, igs_resource_spec_dict, code_resource_spec_dict],
    )

    QF = QueryFactory(
        remote_factory=env.remote_factory,
        local_factory=env.local_factory,
        product_catalog=env.product_catalog,
        parameter_catalog=env.parameter_catalog,
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
        asyncio.run(fetcher.download(fetch_results, env.local_factory, date))
        for fr in found:
            if fr.downloaded:
                print(f"  ✓ {fr.query.server.hostname} → {fr.download_dest}")
            else:
                print(f"  ✗ {fr.query.server.hostname} — download failed")
    else:
        print("\nNo remote files found to download.")
