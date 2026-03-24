#!/usr/bin/env python3
"""Demo: ProductEnvironment public API (Phase 1).

Shows how to construct an environment with a single ``workspace`` argument
and use ``classify()`` to identify product files by filename.

Usage::

    python dev/dev_environment_api.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from gnss_ppp_products.factories import ProductEnvironment


def main() -> None:
    # ── 1. Construction ───────────────────────────────────────────
    # Create a workspace directory (in production this would already exist)
    workspace = Path(tempfile.mkdtemp(prefix="gnss_demo_"))
    print("=" * 64)
    print("ProductEnvironment — Public API Demo")
    print("=" * 64)

    # One-line construction: auto-loads all bundled specs
    env = ProductEnvironment(workspace=workspace)
    print(f"\n>>> env = ProductEnvironment(workspace={str(workspace)!r})")
    print(f"    {env!r}")

    # Alias defaults to the directory stem
    print(f"\n    env.alias      = {env.alias!r}")
    print(f"    env.base_dir   = {env.base_dir}")

    # You can also supply an explicit alias
    env2 = ProductEnvironment(workspace=(workspace, "my-campaign"))
    print(f"\n>>> env2 = ProductEnvironment(workspace=({str(workspace)!r}, 'my-campaign'))")
    print(f"    env2.alias     = {env2.alias!r}")

    # ── 2. Inspect what's loaded ──────────────────────────────────
    products = sorted(env.product_catalog.products.keys())
    centers = sorted(env.remote_factory.centers)
    dep_specs = sorted(env.dependency_specs.keys())

    print(f"\n--- Loaded catalog summary ---")
    print(f"    Products ({len(products)}): {', '.join(products)}")
    print(f"    Centers  ({len(centers)}): {', '.join(centers)}")
    print(f"    Dep specs ({len(dep_specs)}): {', '.join(dep_specs)}")
    print(f"    Local factory: {'yes' if env.local_factory else 'no'}")

    # ── 3. classify() — identify product files ────────────────────
    print(f"\n--- classify() examples ---")
    sample_filenames = [
        "WUM0MGXFIN_20250010000_01D_05M_ORB.SP3.gz",
        "COD0OPSRAP_20251000000_01D_30S_CLK.CLK.gz",
        "GFZ0MGXRAP_20251000000_01D_01D_ERP.ERP.gz",
        "WUM0MGXFIN_20250150000_01D_01D_OSB.BIA.gz",
        "IGS0OPSRAP_20251000000_01D_15M_ORB.SP3",
        "WUM0MGXFIN_20250150000_01D_30S_ATT.OBX.gz",
        "igs20.atx",
        "NCC12500.25o",
        "orography_ell_1x1",
    ]

    for fname in sample_filenames:
        result = env.classify(fname)
        if result is not None:
            params = result["parameters"]
            params_str = ", ".join(f"{k}={v}" for k, v in sorted(params.items()))
            print(f"    {fname}")
            print(f"      → product={result['product']}, center={params.get('AAA', '')!r}, "
                  f"quality={params.get('TTT', '')!r}")
            print(f"        params: {params_str}")
        else:
            print(f"    {fname}")
            print(f"      → NO MATCH")
        print()

    # ── 4. classify() error handling ──────────────────────────────
    print("--- classify() no-match case ---")
    unknown = "totally_random_file.xyz"
    result = env.classify(unknown)
    print(f"    env.classify({unknown!r})")
    print(f"      → {result}")

    # ── 5. Immutability ───────────────────────────────────────────
    print(f"\n--- Immutability ---")
    print(f"    hasattr(env, 'register_remote')          = {hasattr(env, 'register_remote')}")
    print(f"    hasattr(env, 'register_dependency_spec') = {hasattr(env, 'register_dependency_spec')}")
    try:
        env.local_factory = "/some/path"  # type: ignore[assignment]
        print("    env.local_factory setter                 = allowed (unexpected!)")
    except AttributeError:
        print("    env.local_factory setter                 = blocked (AttributeError)")

    print(f"\n{'=' * 64}")
    print("Done.")

    # Cleanup
    workspace.rmdir()


if __name__ == "__main__":
    main()
