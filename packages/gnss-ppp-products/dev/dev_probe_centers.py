"""
dev_probe_centers.py — Probe all center configs for product availability.

Loads every *_config.yaml from configs/centers/, builds a ProductEnvironment,
and for each center × product runs a QueryFactory + ResourceFetcher search
to check file availability.

Usage:
    python dev_probe_centers.py                   # probe all centers
    python dev_probe_centers.py --center WUM COD  # probe only WUM and COD
"""

import argparse
import datetime
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List

import yaml

# Ensure dev/ is on the path for dev_specs
sys.path.append(str(Path(__file__).parent))
from dev_specs import parameter_spec_dict, format_spec_dict, product_spec_dict

from gnss_ppp_products.factories import ProductEnvironment, QueryFactory, ResourceFetcher

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────
CENTERS_DIR = (
    Path(__file__).resolve().parent.parent
    / "src" / "gnss_ppp_products" / "configs" / "centers"
)
LOCAL_CONFIG_PATH = (
    Path(__file__).resolve().parent.parent
    / "src" / "gnss_ppp_products" / "configs" / "local" / "local_config.yaml"
)
OUTPUT_PATH = Path(__file__).resolve().parent / "probe_results.json"


def load_center_configs(center_dir: Path, only: List[str] | None = None) -> List[dict]:
    """Load all *_config.yaml files from the centers directory."""
    configs = []
    for path in sorted(center_dir.glob("*_config*.yaml")):
        with open(path) as f:
            data = yaml.safe_load(f)
        # Skip if filtering and this center isn't requested
        if only and data.get("id", "").upper() not in [c.upper() for c in only]:
            continue
        # Only load files in our ResourceSpec dict format (has product_name on products)
        products = data.get("products", [])
        if products and "product_name" in products[0]:
            configs.append(data)
        else:
            logger.info(f"Skipping {path.name} (old format, missing product_name)")
    return configs


def probe_center(
    center_dict: dict,
    date: datetime.datetime,
    env_base: ProductEnvironment,
    fetcher: ResourceFetcher,
) -> Dict:
    """Probe every product in a single center config for availability."""
    center_id = center_dict["id"]
    center_name = center_dict.get("name", center_id)

    # Build a single-center environment
    env = ProductEnvironment(
        base_dir="/tmp/gnss_probe",  # not used for search, just needed for local factory
        parameter_specs=parameter_spec_dict,
        format_specs=format_spec_dict,
        product_specs=product_spec_dict,
        remote_specs=[center_dict],
    )

    qf = QueryFactory(
        remote_factory=env.remote_factory,
        local_factory=env_base.local_factory,
        product_catalog=env.product_catalog,
        parameter_catalog=env.parameter_catalog,
    )

    center_result = {
        "id": center_id,
        "name": center_name,
        "products": [],
    }

    # Get unique product names offered by this center
    product_names = []
    for p in center_dict.get("products", []):
        pname = p["product_name"]
        if pname not in product_names:
            product_names.append(pname)

    for product_name in product_names:
        # Check if product exists in the product catalog
        if product_name not in env.product_catalog.products:
            center_result["products"].append({
                "product": product_name,
                "status": "SKIP",
                "reason": f"Product spec '{product_name}' not in ProductCatalog",
                "queries": 0,
                "found": 0,
                "files": 0,
                "matches": [],
            })
            continue

        try:
            queries = qf.get(
                date=date,
                product={"name": product_name},
            )
        except Exception as e:
            center_result["products"].append({
                "product": product_name,
                "status": "ERROR",
                "reason": str(e),
                "queries": 0,
                "found": 0,
                "files": 0,
                "matches": [],
            })
            continue

        # Filter to only remote queries for this center
        remote_queries = [
            q for q in queries
            if any(
                s.id in [sv["id"] for sv in center_dict.get("servers", [])]
                for s in [q.server]
            )
        ]

        if not remote_queries:
            center_result["products"].append({
                "product": product_name,
                "status": "NO_QUERIES",
                "reason": "No remote queries generated for this center",
                "queries": 0,
                "found": 0,
                "files": 0,
                "matches": [],
            })
            continue

        results = fetcher.search(remote_queries)
        found_results = [r for r in results if r.found]
        total_files = sum(len(r.matched_filenames) for r in found_results)

        matches = []
        for r in found_results:
            dir_str = ResourceFetcher._get_directory(r.query) or "?"
            matches.append({
                "server": r.query.server.hostname,
                "directory": dir_str,
                "pattern": ResourceFetcher._get_file_pattern(r.query),
                "files": r.matched_filenames[:10],
            })

        errors = []
        for r in results:
            if r.error:
                errors.append({
                    "server": r.query.server.hostname,
                    "directory": ResourceFetcher._get_directory(r.query) or "?",
                    "error": r.error,
                })

        status = "FOUND" if found_results else ("ERROR" if errors else "NOT_FOUND")

        center_result["products"].append({
            "product": product_name,
            "status": status,
            "queries": len(remote_queries),
            "found": len(found_results),
            "files": total_files,
            "matches": matches,
            "errors": errors if errors else [],
        })

    return center_result


def print_summary(results: List[Dict]) -> None:
    """Print a human-readable summary table."""
    print("\n" + "=" * 80)
    print(f"{'CENTER':<10} {'PRODUCT':<14} {'STATUS':<12} {'QUERIES':>8} {'FOUND':>6} {'FILES':>6}")
    print("-" * 80)

    totals = {"queries": 0, "found": 0, "files": 0}

    for center in results:
        first = True
        for prod in center["products"]:
            label = center["id"] if first else ""
            first = False
            status = prod["status"]

            # Color status
            if status == "FOUND":
                status_str = f"\033[92m{status:<12}\033[0m"  # green
            elif status in ("ERROR", "SKIP"):
                status_str = f"\033[91m{status:<12}\033[0m"  # red
            else:
                status_str = f"\033[93m{status:<12}\033[0m"  # yellow

            print(f"{label:<10} {prod['product']:<14} {status_str} {prod['queries']:>8} {prod['found']:>6} {prod['files']:>6}")

            totals["queries"] += prod["queries"]
            totals["found"] += prod["found"]
            totals["files"] += prod["files"]

            # Print first few matched files
            for m in prod.get("matches", [])[:2]:
                files_str = ", ".join(m["files"][:3])
                if len(m["files"]) > 3:
                    files_str += f" (+{len(m['files']) - 3} more)"
                print(f"{'':>10} {'':>14}   {m['server']}: {files_str}")

        print("-" * 80)

    print(f"{'TOTAL':<10} {'':14} {'':12} {totals['queries']:>8} {totals['found']:>6} {totals['files']:>6}")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Probe GNSS data centers for product availability")
    parser.add_argument("--center", nargs="*", help="Only probe these centers (by ID)")
    parser.add_argument("--date", default="2025-01-01", help="Probe date (YYYY-MM-DD)")
    parser.add_argument("--save", action="store_true", help="Save results to probe_results.json")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    date = datetime.datetime.fromisoformat(args.date).replace(tzinfo=datetime.timezone.utc)

    print(f"Probing centers for date {date.date()}...")
    print(f"Loading center configs from {CENTERS_DIR}")

    # Load center configs
    center_configs = load_center_configs(CENTERS_DIR, only=args.center)
    print(f"Found {len(center_configs)} center config(s): {[c['id'] for c in center_configs]}")

    if not center_configs:
        print("No matching center configs found.")
        return

    # Build a base environment (with local factory for the local side of queries)
    env_base = ProductEnvironment(
        base_dir="/tmp/gnss_probe",
        parameter_specs=parameter_spec_dict,
        format_specs=format_spec_dict,
        product_specs=product_spec_dict,
        local_config=LOCAL_CONFIG_PATH,
    )

    fetcher = ResourceFetcher()
    all_results = []

    for center_dict in center_configs:
        print(f"\n--- Probing {center_dict['id']} ({center_dict.get('name', '')}) ---")
        result = probe_center(center_dict, date, env_base, fetcher)
        all_results.append(result)

    print_summary(all_results)

    if args.save:
        with open(OUTPUT_PATH, "w") as f:
            json.dump(all_results, f, indent=2, default=str)
        print(f"\nResults saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
