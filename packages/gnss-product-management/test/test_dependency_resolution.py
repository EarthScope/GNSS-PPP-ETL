"""
Tests: Full dependency resolution workflow.

End-to-end: DependencySpec → ResolvePipeline → DependencyResolution → lockfile.

Uses the multi-centre environment (Wuhan + CODE + CDDIS) with the
PRIDE-PPPAR dependency spec.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ── Paths ──────────────────────────────────────────────────────────
from gnss_management_specs.configs import LOCAL_SPEC_DIR
from gnss_product_management.environments import WorkSpace
from gnss_product_management.factories.pipelines.resolve import ResolvePipeline
from gnss_product_management.specifications.dependencies.dependencies import (
    DependencySpec,
    ResolvedDependency,
)

_TEST_RESOURCES = Path(__file__).resolve().parent / "resources"
PRIDE_PPPAR_SPEC = _TEST_RESOURCES / "pride_pppar.yaml"


# ── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def dep_spec() -> DependencySpec:
    """Load the PRIDE-PPPAR dependency spec from YAML."""
    return DependencySpec.from_yaml(PRIDE_PPPAR_SPEC)


@pytest.fixture(scope="module")
def pipeline(multi_env, tmp_path_factory) -> ResolvePipeline:
    """ResolvePipeline wired to the multi-centre environment."""
    base = tmp_path_factory.mktemp("resolve_test")
    ws = WorkSpace()
    for path in Path(LOCAL_SPEC_DIR).glob("*.yaml"):
        ws.add_resource_spec(path)
    ws.register_spec(base_dir=base, spec_ids=["local_config"])
    return ResolvePipeline(env=multi_env, workspace=ws)


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
# Unit: Pipeline construction (no network)
# ===================================================================


class TestPipelineConstruction:
    def test_pipeline_builds(self, pipeline) -> None:
        assert pipeline is not None


# ===================================================================
# Integration: Resolve with remote search (network required)
# ===================================================================


class TestResolverWithFetcher:
    # Products with confirmed HTTP sources at geodetic data centres.
    _REMOTELY_AVAILABLE = {"ORBIT", "CLOCK", "ERP", "BIA", "ATTATX", "RNX3_BRDC"}

    @pytest.mark.integration
    def test_resolve_finds_remote_products(
        self,
        pipeline,
        dep_spec,
        test_date,
    ) -> None:
        """All products with known HTTP sources should be resolved."""
        resolution, lockfile_path = pipeline.run(dep_spec, test_date, sink_id="local_config")
        by_spec = {r.spec: r for r in resolution.resolved}
        missing_core = [
            spec
            for spec in self._REMOTELY_AVAILABLE
            if by_spec.get(spec, None) and by_spec[spec].status == "missing"
        ]
        assert not missing_core, (
            f"Core products could not be resolved: {missing_core}\n{resolution.table()}"
        )
        print(f"\nResolution table for {test_date.isoformat()}:\n")
        print(resolution.table())
        print(f"{'-' * 60}\n")

    @pytest.mark.integration
    def test_resolve_populates_remote_url(
        self,
        pipeline,
        dep_spec,
        test_date,
    ) -> None:
        """Downloaded products should have a remote_url set."""
        resolution, _ = pipeline.run(dep_spec, test_date, sink_id="local_config")
        for r in resolution.resolved:
            if r.status == "downloaded":
                assert r.remote_url, f"{r.spec} has empty remote_url"

    @pytest.mark.integration
    def test_resolution_summary(self, pipeline, dep_spec, test_date) -> None:
        resolution, _ = pipeline.run(dep_spec, test_date, sink_id="local_config")
        summary = resolution.summary()
        assert "pride-pppar" in summary
        assert "15 deps" in summary

    @pytest.mark.integration
    def test_resolution_table(self, pipeline, dep_spec, test_date) -> None:
        resolution, _ = pipeline.run(dep_spec, test_date, sink_id="local_config")
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
