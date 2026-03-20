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

    # ── Narrowed query (parameters specified) ────────────────────
    print("\n" + "=" * 60)
    print("NARROWED query: parameters={'AAA': ['WUM','WMC']}")
    print("=" * 60)
    test_narrowed = QF.get(
        date=date,
        product={"name": "ORBIT", "version": ["1"]},
        parameters={"AAA": ["WUM", "WMC"]},
    )

    fetcher = ResourceFetcher()
    results_narrowed = fetcher.search(test_narrowed)
    found_narrowed = [fr for fr in results_narrowed if fr.found]
    print(f"\nNarrowed: {len(test_narrowed)} queries → {len(found_narrowed)} found, "
          f"{sum(len(fr.matched_filenames) for fr in found_narrowed)} files")
    for fr in found_narrowed:
        dir_str = ResourceFetcher._get_directory(fr.query) or "?"
        print(f"  [{fr.query.server.hostname}] {dir_str} → {fr.matched_filenames[:5]}")

    # ── Wide query (no parameters) ───────────────────────────────
    print("\n" + "=" * 60)
    print("WIDE query: parameters omitted")
    print("=" * 60)
    test_wide = QF.get(
        date=date,
        product={"name": "ORBIT", "version": ["1"]},
    )

    results_wide = fetcher.search(test_wide)
    found_wide = [fr for fr in results_wide if fr.found]
    print(f"\nWide: {len(test_wide)} queries → {len(found_wide)} found, "
          f"{sum(len(fr.matched_filenames) for fr in found_wide)} files")
    for fr in found_wide:
        dir_str = ResourceFetcher._get_directory(fr.query) or "?"
        print(f"  [{fr.query.server.hostname}] {dir_str} → {fr.matched_filenames[:5]}")

    # ── Comparison ───────────────────────────────────────────────
    print("\n" + "=" * 60)
    n_files = sum(len(fr.matched_filenames) for fr in found_narrowed)
    w_files = sum(len(fr.matched_filenames) for fr in found_wide)
    print(f"Narrowed: {n_files} files  |  Wide: {w_files} files  |  Δ = +{w_files - n_files}")
    print("=" * 60)

    fetch_results = results_wide
    found = found_wide

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
