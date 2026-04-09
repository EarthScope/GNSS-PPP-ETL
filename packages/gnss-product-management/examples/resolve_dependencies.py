"""Resolve and download all dependencies for a date.

Demonstrates the full dependency resolution pipeline using
:class:`GNSSClient`, which wraps :class:`ResolvePipeline` internally.

Products already present on disk are detected automatically via lockfiles;
missing products are downloaded from remote servers.
"""

import datetime
from pathlib import Path

from gnss_product_management import GNSSClient
from gnss_product_management.specifications.dependencies.dependencies import (
    DependencySpec,
)

# --- 1. Configure client with local storage --------------------------------
base_dir = Path("/data/gnss-products")  # <-- change to your path
client = GNSSClient.from_defaults(base_dir=base_dir)

# --- 2. Load the dependency spec -------------------------------------------
dep_spec = DependencySpec.from_yaml(
    "/path/to/configs/dependencies/pride_pppar.yaml"  # <-- change to your path
)

# --- 3. Resolve all dependencies for a target date -------------------------
date = datetime.datetime(2025, 1, 2, tzinfo=datetime.timezone.utc)
resolution, lockfile_path = client.resolve_dependencies(dep_spec, date, sink_id="local")

# --- 4. Inspect results ----------------------------------------------------
print(resolution.summary())
print()
print(resolution.table())
print()

if resolution.all_required_fulfilled:
    print("All required products resolved.")
    paths = resolution.product_paths()
    for spec, path in paths.items():
        print(f"  {spec:<14s} -> {path}")
else:
    print("Missing required products:")
    for dep in resolution.missing:
        if dep.required:
            print(f"  {dep.spec}")

if lockfile_path:
    print(f"\nLockfile written to: {lockfile_path}")
