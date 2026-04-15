"""Parametrized sweep across every (center, product) pair in the YAML specs.

Two test tiers
--------------
TestQueryExpansion
    Unit tests — no network.  Verify that SearchPlanner generates at least one
    remote query candidate for every (center, product) combination declared in
    the center configs, and that each query carries a resolved directory and a
    filename regex pattern.

TestRemoteProbe
    Integration tests — hits live servers.  For every (center, product) pair,
    perform a real directory listing and assert that at least one file is
    matched.  Run with ``-m integration`` to include.

The parametrize lists are built at import time by parsing the YAML files under
gpm_specs, so new centers and products are picked up automatically.
"""

from __future__ import annotations

import datetime
from functools import cache
from pathlib import Path

import pytest
import yaml
from conftest import _build_env
from gnss_product_management.environments import WorkSpace
from gnss_product_management.factories import SearchPlanner
from gpm_specs.configs import CENTERS_RESOURCE_DIR

# ── Static reference table products not reachable on the standard test date ──
# These are fetched by a different mechanism (static URL, no date directory).
# They are included in the query-expansion tier but skipped for remote probes.
_SKIP_REMOTE: frozenset[str] = frozenset(
    {
        "LEO_L1B",  # GFZ: requires specific mission data windows
    }
)

# Reference date shared with the rest of the test suite.
_DATE = datetime.datetime(2025, 1, 15, tzinfo=datetime.timezone.utc)


# ── Discover all (center_yaml, center_id, product_name) at import time ────────


def _discover_center_products() -> list[tuple[str, str, str]]:
    """Parse every *_config.yaml and return unique (yaml_file, center_id, product_name)."""
    seen: set[tuple[str, str, str]] = set()
    entries: list[tuple[str, str, str]] = []
    for yaml_file in sorted(Path(CENTERS_RESOURCE_DIR).glob("*_config.yaml")):
        cfg = yaml.safe_load(yaml_file.read_text())
        center_id: str = cfg.get("id", yaml_file.stem)
        for product_entry in cfg.get("products", []):
            if not product_entry.get("available", True):
                continue  # skip explicitly disabled products
            product_name: str | None = product_entry.get("product_name")
            if product_name:
                key = (yaml_file.name, center_id, product_name)
                if key not in seen:
                    seen.add(key)
                    entries.append(key)
    return entries


_CENTER_PRODUCTS: list[tuple[str, str, str]] = _discover_center_products()
_IDS: list[str] = [f"{cid}/{pname}" for (_, cid, pname) in _CENTER_PRODUCTS]


# ── Cached planner per center ─────────────────────────────────────────────────


@cache
def _planner_for(center_yaml: str) -> SearchPlanner:
    """Build and cache a SearchPlanner for a single center config.

    Uses an empty WorkSpace because we only exercise remote query paths;
    local/file targets are filtered out before assertions.
    """
    env = _build_env(center_yaml)
    return SearchPlanner(product_registry=env, workspace=WorkSpace())


# ── Shared helpers ────────────────────────────────────────────────────────────


def _remote_queries(qf: SearchPlanner, product_name: str) -> list:
    """Return query candidates whose protocol is not FILE or LOCAL."""
    queries = qf.get(date=_DATE, product={"name": product_name})
    return [q for q in queries if (q.server.protocol or "").upper() not in ("FILE", "LOCAL", "")]


# ── Tier 1: Query expansion (unit, no network) ────────────────────────────────


class TestQueryExpansion:
    """Verify SearchPlanner produces valid remote query templates for every
    (center, product) pair declared in the YAML specs."""

    @pytest.mark.parametrize(
        "center_yaml,center_id,product_name",
        _CENTER_PRODUCTS,
        ids=_IDS,
    )
    def test_generates_remote_queries(
        self,
        center_yaml: str,
        center_id: str,
        product_name: str,
    ) -> None:
        """SearchPlanner must return at least one non-local query."""
        qf = _planner_for(center_yaml)
        queries = _remote_queries(qf, product_name)
        assert queries, f"{center_id}/{product_name}: SearchPlanner produced 0 remote queries"

    @pytest.mark.parametrize(
        "center_yaml,center_id,product_name",
        _CENTER_PRODUCTS,
        ids=_IDS,
    )
    def test_query_has_resolved_directory(
        self,
        center_yaml: str,
        center_id: str,
        product_name: str,
    ) -> None:
        """Every remote query must carry a non-empty directory (pattern or value)."""
        qf = _planner_for(center_yaml)
        for q in _remote_queries(qf, product_name):
            directory = q.directory.value or q.directory.pattern
            assert directory, f"{center_id}/{product_name}: query has empty directory field"

    @pytest.mark.parametrize(
        "center_yaml,center_id,product_name",
        _CENTER_PRODUCTS,
        ids=_IDS,
    )
    def test_query_has_filename_pattern(
        self,
        center_yaml: str,
        center_id: str,
        product_name: str,
    ) -> None:
        """Every remote query must carry a filename regex pattern for directory matching."""
        qf = _planner_for(center_yaml)
        for q in _remote_queries(qf, product_name):
            assert q.product.filename and q.product.filename.pattern, (
                f"{center_id}/{product_name}: query has no filename pattern"
            )


# ── Tier 2: Remote probe (integration, hits live servers) ─────────────────────


@pytest.mark.integration
class TestRemoteProbe:
    """Hit every registered (center, product) server and assert ≥1 file is found.

    Products in ``_SKIP_REMOTE`` are skipped (no date-specific directory).
    Run this class with ``pytest -m integration``.
    """

    @pytest.mark.parametrize(
        "center_yaml,center_id,product_name",
        _CENTER_PRODUCTS,
        ids=_IDS,
    )
    def test_product_found_on_server(
        self,
        center_yaml: str,
        center_id: str,
        product_name: str,
        fetcher,
    ) -> None:
        """At least one file must be returned from the remote directory listing."""
        if product_name in _SKIP_REMOTE:
            pytest.skip(f"{product_name} excluded from automated remote probes")

        qf = _planner_for(center_yaml)
        queries = _remote_queries(qf, product_name)
        if not queries:
            pytest.skip(f"{center_id}/{product_name}: no remote queries generated")

        results = fetcher.search(queries)
        found = [r for r in results if r.product.filename and r.product.filename.value]
        assert found, (
            f"{center_id}/{product_name}: 0 files found on server "
            f"({len(results)} directory entries returned, 0 matched filename pattern)"
        )
