"""Resolve and download all dependencies for a date.

Demonstrates the full dependency resolution pipeline: builds a
DependencyResolver from a dependency spec YAML, registers a local
workspace directory, and resolves all required products (orbits,
clocks, biases, ERP, ionosphere, etc.).

Products already present on disk are detected automatically via
lockfiles; missing products are downloaded from remote servers.
"""

import datetime
from pathlib import Path
from gnss_product_management import DependencyResolver
from gnss_product_management.defaults import DefaultProductEnvironment, DefaultWorkSpace
from gnss_product_management.specifications.dependencies.dependencies import (
    DependencySpec,
)

# --- 1. Configure local storage -----------------------------------------
# Register a local directory tree where products will be stored.
# "local_config" maps date-based subdirectories (see configs/local/).
workspace = DefaultWorkSpace
base_dir = Path("/data/gnss-products")  # <-- change to your path
workspace.register_spec(base_dir=base_dir, spec_ids=["local_config"], alias="local")

# --- 2. Build the resolver -----------------------------------------------
env = DefaultProductEnvironment
dep_spec = DependencySpec.from_yaml(
    "/Users/franklyndunbar/Project/SeaFloorGeodesy/GNSS-PPP-ETL/packages/pride-ppp/src/pride_ppp/configs/dependencies/pride_pppar.yaml"
)


resolver = DependencyResolver(
    dep_spec=dep_spec,
    product_environment=env,
    query_factory=qf,
    fetcher=fetcher,
)

# --- 3. Resolve all dependencies for a target date ----------------------
date = datetime.datetime(2025, 1, 2, tzinfo=datetime.timezone.utc)
resolution, lockfile_path = resolver.resolve(date=date, local_sink_id="local")

# --- 4. Inspect results --------------------------------------------------
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
