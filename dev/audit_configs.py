"""Audit existing center configs by probing each server for a test date.

For each configured center, this script:
  1. Connects to its registered server(s)
  2. Lists the product directory for PROBE_DATE
  3. Checks that at least one file matching each configured product spec exists
  4. Reports PASS / WARN / FAIL per product entry

Usage (from repo root):
    uv run packages/gnss-product-management/dev/audit_configs.py

Set PROBE_DATE to a date where final products are guaranteed to exist
(>= 14 days in the past).  The script does NOT download anything.

Exit codes: 0 = all PASS, 1 = any FAIL.
"""

from __future__ import annotations

import datetime
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

# ── Config ───────────────────────────────────────────────────────────────────
PROBE_DATE = datetime.datetime(2025, 1, 15, tzinfo=datetime.timezone.utc)

CENTERS_DIR = (
    Path(__file__).parent.parent.parent.parent
    / "gnss-management-specs"
    / "src"
    / "gnss_management_specs"
    / "configs"
    / "centers"
)

# IGS long-filename regex (permissive — matches compressed and uncompressed)
_IGS_LONG = re.compile(
    r"^[A-Z0-9]{3}\d[A-Z0-9]{3}[A-Z]{3}_\d{11}_\d{2}[DHMS]_\d{2}[DHMS]_[A-Z]{3}\.[A-Z0-9]{2,4}",
    re.IGNORECASE,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _gps_week(dt: datetime.datetime) -> int:
    gps_epoch = datetime.datetime(1980, 1, 6, tzinfo=datetime.timezone.utc)
    return (dt - gps_epoch).days // 7


def _fill(template: str, dt: datetime.datetime) -> str:
    week = _gps_week(dt)
    return (
        template.replace("{GPSWEEK}", str(week))
        .replace("{YYYY}", str(dt.year))
        .replace("{DDD}", f"{dt.timetuple().tm_yday:03d}")
        .replace("{HH}", "00")
        .replace("{MM}", "00")
    )


def _list_ftp(hostname: str, path: str, protocol: str) -> list[str] | None:
    try:
        import fsspec  # noqa: PLC0415
    except ImportError:
        print("  [SKIP] fsspec not installed — run: uv add fsspec")
        return None

    host = hostname.split("://")[-1].rstrip("/")
    try:
        ssl = protocol == "ftps"
        fs = fsspec.filesystem("ftp", host=host, ssl=ssl)
        entries: list[str] = fs.ls("/" + path.lstrip("/"), detail=False)
        return [e.split("/")[-1] for e in entries]
    except Exception:
        return None  # caller logs the failure


def _list_https(hostname: str, path: str) -> list[str] | None:
    """Attempt a HEAD request to verify reachability (no directory listing)."""
    try:
        import urllib.request  # noqa: PLC0415

        url = hostname.rstrip("/") + "/" + path.lstrip("/")
        req = urllib.request.Request(
            url, method="HEAD", headers={"User-Agent": "GNSS-PPP-ETL/audit"}
        )
        urllib.request.urlopen(req, timeout=15)
        return []  # reachable but no listing
    except Exception:
        return None


# ── Product spec → filename constraint patterns ──────────────────────────────
# Maps product spec name to (CNT, FMT) pairs for quick filename filtering.
_SPEC_CONSTRAINTS: dict[str, list[tuple[str, str]]] = {
    "ORBIT": [("ORB", "SP3")],
    "CLOCK": [("CLK", "CLK")],
    "ERP": [("ERP", "ERP")],
    "BIA": [("OSB", "BIA")],
    "ATTOBX": [("ATT", "OBX")],
    "IONEX": [("GIM", "INX")],
}


def _matches_product(filename: str, product_name: str, aaa_values: list[str]) -> bool:
    """Return True if *filename* looks like the given product from one of the ACs."""
    constraints = _SPEC_CONSTRAINTS.get(product_name, [])
    name_upper = filename.upper()

    # Check AAA prefix
    ac_match = any(name_upper.startswith(aaa.upper()) for aaa in aaa_values)
    if not ac_match:
        return False

    # Check CNT.FMT suffix
    for cnt, fmt in constraints:
        if f"_{cnt}.{fmt}" in name_upper or f"_{cnt}.{fmt}." in name_upper:
            return True
    return False


@dataclass
class AuditResult:
    center_id: str
    product_id: str
    product_name: str
    server_id: str
    directory: str
    status: str  # PASS | WARN | FAIL | SKIP
    details: str
    example_file: str = ""


def audit_center(config: dict) -> list[AuditResult]:
    results: list[AuditResult] = []

    center_id: str = config.get("id", "?")
    servers: list[dict] = config.get("servers", [])
    products: list[dict] = config.get("products", [])

    server_map = {s["id"]: s for s in servers}
    # Cache directory listing per (server_id, directory) to avoid repeat calls
    dir_cache: dict[tuple[str, str], list[str] | None] = {}

    for product in products:
        product_id: str = product.get("id", "?")
        product_name: str = product.get("product_name", "?")
        server_id: str = product.get("server_id", "?")
        dir_pattern: str = product.get("directory", {}).get("pattern", "")
        directory: str = _fill(dir_pattern, PROBE_DATE)

        server = server_map.get(server_id)
        if not server:
            results.append(
                AuditResult(
                    center_id,
                    product_id,
                    product_name,
                    server_id,
                    directory,
                    "FAIL",
                    f"server_id '{server_id}' not found in config",
                )
            )
            continue

        hostname: str = server["hostname"]
        protocol: str = server.get("protocol", "ftp")

        cache_key = (server_id, directory)
        if cache_key not in dir_cache:
            if protocol in ("ftp", "ftps"):
                listing = _list_ftp(hostname, directory, protocol)
            elif protocol == "https":
                listing = _list_https(hostname, directory)
            else:
                listing = None
            dir_cache[cache_key] = listing

        listing = dir_cache[cache_key]

        if listing is None:
            results.append(
                AuditResult(
                    center_id,
                    product_id,
                    product_name,
                    server_id,
                    directory,
                    "FAIL",
                    f"Could not list {hostname}/{directory}",
                )
            )
            continue

        if not listing:
            # HTTPS hit (reachable, no listing) — mark WARN
            results.append(
                AuditResult(
                    center_id,
                    product_id,
                    product_name,
                    server_id,
                    directory,
                    "WARN",
                    "Server reachable but directory listing not supported (HTTPS)",
                )
            )
            continue

        # Collect expected AAA values for this product entry
        aaa_values = [p["value"] for p in product.get("parameters", []) if p.get("name") == "AAA"]

        # Find matching files
        matches = [f for f in listing if _matches_product(f, product_name, aaa_values)]

        if matches:
            results.append(
                AuditResult(
                    center_id,
                    product_id,
                    product_name,
                    server_id,
                    directory,
                    "PASS",
                    f"{len(matches)} file(s) matched",
                    example_file=matches[0],
                )
            )
        else:
            # Files listed but none matched — could be a naming convention change
            igs_files = [f for f in listing if _IGS_LONG.match(f)]
            results.append(
                AuditResult(
                    center_id,
                    product_id,
                    product_name,
                    server_id,
                    directory,
                    "WARN",
                    (
                        f"Directory OK ({len(listing)} entries, "
                        f"{len(igs_files)} IGS long-format), "
                        f"no match for product_name={product_name} aaa={aaa_values}"
                    ),
                )
            )

    return results


def _status_icon(status: str) -> str:
    return {"PASS": "✓", "WARN": "⚠", "FAIL": "✗", "SKIP": "–"}.get(status, "?")


def main() -> int:
    if not CENTERS_DIR.exists():
        print(f"ERROR: centers dir not found: {CENTERS_DIR}", file=sys.stderr)
        return 1

    config_files = sorted(CENTERS_DIR.glob("*.yaml"))
    if not config_files:
        print(f"No YAML files found in {CENTERS_DIR}", file=sys.stderr)
        return 1

    week = _gps_week(PROBE_DATE)
    print(
        f"Auditing center configs\n"
        f"  Config dir  : {CENTERS_DIR}\n"
        f"  Reference   : {PROBE_DATE.date()}  (GPS week {week})\n"
        f"  Files       : {', '.join(f.name for f in config_files)}\n"
    )

    all_results: list[AuditResult] = []
    for config_file in config_files:
        with config_file.open() as fh:
            config = yaml.safe_load(fh)
        print(f"{'─' * 60}")
        print(f"  [{config.get('id', '?')}] {config_file.name}")
        results = audit_center(config)
        all_results.extend(results)

        for r in results:
            icon = _status_icon(r.status)
            ex = f"  → {r.example_file}" if r.example_file else ""
            print(f"    {icon} [{r.status:<4s}] {r.product_id:<30s}  {r.details}{ex}")
        print()

    # Summary
    counts = {
        s: sum(1 for r in all_results if r.status == s) for s in ("PASS", "WARN", "FAIL", "SKIP")
    }
    print("\nSummary: " + "  ".join(f"{_status_icon(s)} {s}: {n}" for s, n in counts.items()))

    if counts["FAIL"] > 0:
        print(f"\n{counts['FAIL']} product(s) FAILED — review server paths and AAA codes.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
