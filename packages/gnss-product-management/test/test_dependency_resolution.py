"""
Tests: Full dependency resolution workflow.

End-to-end: DependencySpec → DependencyResolver → DependencyResolution → lockfile.

Uses the multi-centre environment (Wuhan + CODE + CDDIS) with the
PRIDE-PPPAR dependency spec.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gnss_product_management.factories import (
    WorkSpace,
    SearchPlanner,
    WormHole,
)
from gnss_product_management.specifications.dependencies.dependencies import (
    DependencySpec,
    ResolvedDependency,
)
from gnss_product_management.factories.dependency_resolver import (
    DependencyResolver,
)


# ── Paths ──────────────────────────────────────────────────────────

from gnss_management_specs.configs import LOCAL_SPEC_DIR

_TEST_RESOURCES = Path(__file__).resolve().parent / "resources"
PRIDE_PPPAR_SPEC = _TEST_RESOURCES / "pride_pppar.yaml"


# ── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def dep_spec() -> DependencySpec:
    """Load the PRIDE-PPPAR dependency spec from YAML."""
    return DependencySpec.from_yaml(PRIDE_PPPAR_SPEC)


@pytest.fixture(scope="module")
def resolver(multi_env, workspace, dep_spec, tmp_path_factory) -> DependencyResolver:
    """DependencyResolver wired to the multi-centre environment."""
    base = tmp_path_factory.mktemp("resolve_test")
    ws = WorkSpace()
    for path in Path(LOCAL_SPEC_DIR).glob("*.yaml"):
        ws.add_resource_spec(path)
    ws.register_spec(base_dir=base, spec_ids=["local_config"])
    qf = SearchPlanner(product_registry=multi_env, workspace=ws)
    fetcher = WormHole(env=multi_env)
    return DependencyResolver(
        dep_spec,
        query_factory=qf,
        product_environment=multi_env,
        fetcher=fetcher,
    )


# ===================================================================
# Unit: DependencySpec loading
# ===================================================================


class TestDependencySpecLoading:
    def test_spec_file_exists(self) -> None:
        assert PRIDE_PPPAR_SPEC.exists()

    def test_spec_loads(self, dep_spec) -> None:
        assert dep_spec.name == "pride-pppar"

    def test_spec_has_dependencies(self, dep_spec) -> None:
        assert len(dep_spec.dependencies) == 15

    def test_spec_has_preferences(self, dep_spec) -> None:
        assert len(dep_spec.preferences) == 2

    def test_preference_parameters(self, dep_spec) -> None:
        params = [p.parameter for p in dep_spec.preferences]
        assert "AAA" in params
        assert "TTT" in params

    def test_required_dependencies(self, dep_spec) -> None:
        required = [d for d in dep_spec.dependencies if d.required]
        assert len(required) == 15
        specs = {d.spec for d in required}
        assert specs >= {
            "ORBIT",
            "CLOCK",
            "ERP",
            "BIA",
            "ATTOBX",
            "ATTATX",
            "RNX3_BRDC",
            "LEAP_SEC",
            "SAT_PARAMS",
        }

    def test_optional_dependencies(self, dep_spec) -> None:
        optional = [d for d in dep_spec.dependencies if not d.required]
        assert len(optional) == 0


# ===================================================================
# Unit: Resolver construction (no network)
# ===================================================================


class TestResolverConstruction:
    def test_resolver_builds(self, resolver) -> None:
        assert resolver is not None
        assert resolver.dep_spec.name == "pride-pppar"


# ===================================================================
# Integration: Resolve with remote search (network required)
# ===================================================================


class TestResolverWithFetcher:
    @pytest.mark.integration
    def test_resolve_finds_remote_products(
        self,
        resolver,
        test_date,
    ) -> None:
        """At least some products should be found remotely."""
        resolution, lockfile_path = resolver.resolve(
            test_date, local_sink_id="local_config"
        )
        found = [r.status != "missing" for r in resolution.resolved]

        assert all(found), f"Expected no missing product.\n{resolution.table()}"
        print(f"\nResolution table for {test_date.isoformat()}:\n")
        print(resolution.table())
        print(f"{'-' * 60}\n")

    @pytest.mark.integration
    def test_resolve_populates_remote_url(
        self,
        resolver,
        test_date,
    ) -> None:
        """Found products should have a remote_url set."""
        resolution, _ = resolver.resolve(test_date, local_sink_id="local_config")
        for r in resolution.resolved:
            if r.status != "missing":
                assert r.remote_url, f"{r.spec} has empty remote_url"

    @pytest.mark.integration
    def test_resolution_summary(self, resolver, test_date) -> None:
        resolution, _ = resolver.resolve(test_date, local_sink_id="local_config")
        summary = resolution.summary()
        assert "pride-pppar" in summary
        assert "9 deps" in summary

    @pytest.mark.integration
    def test_resolution_table(self, resolver, test_date) -> None:
        resolution, _ = resolver.resolve(test_date, local_sink_id="local_config")
        table = resolution.table()
        assert "ORBIT" in table
        assert "CLOCK" in table


# ===================================================================
# Unit: Lockfile models
# ===================================================================


class TestLockfileModels:
    def test_resolved_lockfile_attached(self) -> None:
        """ResolvedDependency can carry a remote_url."""
        resolved = ResolvedDependency(
            spec="CLOCK",
            required=True,
            status="remote",
            remote_url="ftp://host/dir/clock.clk",
        )
        assert resolved.remote_url == "ftp://host/dir/clock.clk"
