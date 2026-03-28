"""
Tests: Full dependency resolution workflow.

End-to-end: DependencySpec → DependencyResolver → DependencyResolution → lockfile.

Uses the multi-centre environment (Wuhan + CODE + CDDIS) with the
PRIDE-PPPAR dependency spec.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path

import pytest

from gnss_ppp_products.factories import (
    ProductEnvironment,
    QueryFactory,
    ResourceFetcher,
)
from gnss_ppp_products.specifications.dependencies.dependencies import (
    DependencyResolution,
    DependencySpec,
    ResolvedDependency,
)
from gnss_ppp_products.factories.dependency_resolver import (
    DependencyResolver,
)
from gnss_ppp_products.lockfile import (
    DependencyLockFile as ProductLockfile,
)


# ── Paths ──────────────────────────────────────────────────────────

_CONFIGS_DIR = (
    Path(__file__).resolve().parent.parent / "src" / "gnss_ppp_products" / "configs"
)
PRIDE_PPPAR_SPEC = _CONFIGS_DIR / "dependencies" / "pride_pppar.yaml"


# ── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def dep_spec() -> DependencySpec:
    """Load the PRIDE-PPPAR dependency spec from YAML."""
    return DependencySpec.from_yaml(PRIDE_PPPAR_SPEC)


@pytest.fixture(scope="module")
def resolver(multi_env, dep_spec, tmp_path_factory) -> DependencyResolver:
    """DependencyResolver wired to the multi-centre environment."""
    base = tmp_path_factory.mktemp("resolve_test")
    qf = QueryFactory(
        remote_factory=multi_env.remote_factory,
        local_factory=multi_env.local_factory,
        product_catalog=multi_env.product_catalog,
        parameter_catalog=multi_env.parameter_catalog,
    )
    return DependencyResolver(
        dep_spec,
        base_dir=base,
        query_factory=qf,
    )


@pytest.fixture(scope="module")
def resolver_with_fetcher(multi_env, dep_spec, tmp_path_factory) -> DependencyResolver:
    """DependencyResolver with a ResourceFetcher for remote probing."""
    base = tmp_path_factory.mktemp("resolve_fetch_test")
    qf = QueryFactory(
        remote_factory=multi_env.remote_factory,
        local_factory=multi_env.local_factory,
        product_catalog=multi_env.product_catalog,
        parameter_catalog=multi_env.parameter_catalog,
    )
    fetcher = ResourceFetcher()
    return DependencyResolver(
        dep_spec,
        base_dir=base,
        query_factory=qf,
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
        assert len(dep_spec.dependencies) == 9

    def test_spec_has_preferences(self, dep_spec) -> None:
        assert len(dep_spec.preferences) == 2

    def test_preference_parameters(self, dep_spec) -> None:
        params = [p.parameter for p in dep_spec.preferences]
        assert "AAA" in params
        assert "TTT" in params

    def test_required_dependencies(self, dep_spec) -> None:
        required = [d for d in dep_spec.dependencies if d.required]
        assert len(required) == 9
        specs = {d.spec for d in required}
        assert specs == {
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

    def test_resolve_without_fetcher(self, resolver, test_date) -> None:
        """Without a fetcher, remote products remain 'missing'."""
        resolution = resolver.resolve(test_date)
        assert isinstance(resolution, DependencyResolution)
        assert resolution.spec_name == "pride-pppar"
        assert len(resolution.resolved) == 9

    def test_resolution_summary(self, resolver, test_date) -> None:
        resolution = resolver.resolve(test_date)
        summary = resolution.summary()
        assert "pride-pppar" in summary
        assert "9 deps" in summary

    def test_resolution_table(self, resolver, test_date) -> None:
        resolution = resolver.resolve(test_date)
        table = resolution.table()
        assert "ORBIT" in table
        assert "CLOCK" in table


# ===================================================================
# Integration: Resolve with remote search (network required)
# ===================================================================

pytestmark_integration = pytest.mark.integration


class TestResolverWithFetcher:
    @pytest.mark.integration
    def test_resolve_finds_remote_products(
        self,
        resolver_with_fetcher,
        test_date,
    ) -> None:
        """At least some products should be found remotely."""
        resolution = resolver_with_fetcher.resolve(test_date)
        found = [r.status != "missing" for r in resolution.resolved]

        assert all(found), f"Expected at  no missing product.\n{resolution.table()}"
        print(f"\nResolution table for {test_date.isoformat()}:\n")
        print(resolution.table())
        print(f"{'-' * 60}\n")

    @pytest.mark.integration
    def test_resolve_populates_remote_url(
        self,
        resolver_with_fetcher,
        test_date,
    ) -> None:
        """Found products should have a remote_url set."""
        resolution = resolver_with_fetcher.resolve(test_date)
        for r in resolution.resolved:
            if r.status != "missing":
                assert r.remote_url, f"{r.spec} has empty remote_url"

    @pytest.mark.integration
    def test_lockfile_from_resolution(
        self,
        resolver_with_fetcher,
        test_date,
    ) -> None:
        """Resolution can produce a valid lockfile."""
        resolution = resolver_with_fetcher.resolve(test_date)
        lockfile = resolution.to_lockfile(date=test_date.isoformat())
        assert isinstance(lockfile, ProductLockfile)
        assert lockfile.requires_date == test_date.isoformat()
        assert lockfile.version == 1
        print(f"\nLockfile for resolution on {test_date.isoformat()}:\n")
        print(lockfile.model_dump_json(indent=2))
        print(f"{'-' * 60}\n")

    @pytest.mark.integration
    def test_lockfile_json_roundtrip(
        self,
        resolver_with_fetcher,
        test_date,
    ) -> None:
        """Lockfile serializes to JSON and parses back identically."""
        resolution = resolver_with_fetcher.resolve(test_date)
        lockfile = resolution.to_lockfile(date=test_date.isoformat())
        json_str = lockfile.to_json()
        parsed = ProductLockfile.from_json(json_str)
        assert len(parsed.products) == len(lockfile.products)
        for orig, rt in zip(lockfile.products, parsed.products):
            assert orig.name == rt.name
            assert orig.url == rt.url

    @pytest.mark.integration
    def test_lockfile_products_match_found(
        self,
        resolver_with_fetcher,
        test_date,
    ) -> None:
        """Each locked product corresponds to a found resolution."""
        resolution = resolver_with_fetcher.resolve(test_date)
        lockfile = resolution.to_lockfile(date=test_date.isoformat())
        found_specs = {
            r.spec
            for r in resolution.resolved
            if r.status != "missing" and r.remote_url
        }
        locked_names = {p.name for p in lockfile.products}
        assert locked_names == found_specs

    @pytest.mark.integration
    def test_preference_ordering_respected(
        self,
        resolver_with_fetcher,
        test_date,
    ) -> None:
        """Products from preferred centres should appear with lower ranks."""
        resolution = resolver_with_fetcher.resolve(test_date)
        for r in resolution.resolved:
            if r.status != "missing" and r.preference_label:
                # preference_rank should be a non-negative int for remote
                assert r.preference_rank >= 0 or r.preference_label == "local"


# ===================================================================
# Unit: Per-file lockfile sidecar
# ===================================================================


class TestFileLockSidecar:
    def test_hash_file(self, tmp_path) -> None:
        """_hash_file returns a sha256-prefixed hex digest."""
        from gnss_ppp_products.factories.dependency_resolver import _hash_file

        p = tmp_path / "sample.sp3"
        p.write_bytes(b"hello world")
        h = _hash_file(p)
        assert h.startswith("sha256:")
        assert len(h) == len("sha256:") + 64

    def test_write_file_lock_creates_sidecar(self, tmp_path) -> None:
        """_write_file_lock writes a .lock JSON file beside the downloaded file."""
        from gnss_ppp_products.lockfile import LockProduct

        local = tmp_path / "WUM0MGXFIN_20240010000_01D_05M_ORB.SP3.gz"
        local.write_bytes(b"fake orbit data")

        lock = LockProduct(
            name="ORBIT",
            format="SP3",
            version="FIN",
            variant="MGX",
            description="Precise satellite orbits",
            required=True,
            url="ftp://host/dir/WUM0MGXFIN_20240010000_01D_05M_ORB.SP3.gz",
            regex=r"WUM\dMGXFIN_20240010000_01D_05M_ORB\.SP3.*",
            hash="sha256:abcd1234",
            size=15,
        )

        resolved = ResolvedDependency(
            spec="ORBIT",
            required=True,
            status="downloaded",
            local_path=local,
            remote_url="ftp://host/dir/WUM0MGXFIN_20240010000_01D_05M_ORB.SP3.gz",
            regex=r"WUM\dMGXFIN_20240010000_01D_05M_ORB\.SP3.*",
            hash="sha256:abcd1234",
            size=15,
            format="SP3",
            version="FIN",
            variant="MGX",
            description="Precise satellite orbits",
            lockfile=lock,
        )

        DependencyResolver._write_file_lock(local, resolved)

        lock_path = tmp_path / "WUM0MGXFIN_20240010000_01D_05M_ORB.SP3.gz.lock"
        assert lock_path.exists()
        import json

        data = json.loads(lock_path.read_text())
        assert data["name"] == "ORBIT"
        assert data["hash"] == "sha256:abcd1234"
        assert data["size"] == 15
        assert data["url"] == "ftp://host/dir/WUM0MGXFIN_20240010000_01D_05M_ORB.SP3.gz"
        assert data["local_path"] == str(local)

    def test_resolved_lockfile_attached(self, tmp_path) -> None:
        """ResolvedDependency.lockfile is a LockProduct instance."""
        from gnss_ppp_products.lockfile import LockProduct

        resolved = ResolvedDependency(
            spec="CLOCK",
            required=True,
            status="remote",
            remote_url="ftp://host/dir/clock.clk",
            lockfile=LockProduct(
                name="CLOCK",
                url="ftp://host/dir/clock.clk",
                required=True,
            ),
        )
        assert resolved.lockfile is not None
        assert resolved.lockfile.name == "CLOCK"
        assert resolved.lockfile.url == "ftp://host/dir/clock.clk"
