# Functionality Spec: Dependency Lockfiles

**Date**: 2026-03-29
**Status**: Draft
**Scope**: Station-independent, version-keyed lockfile subsystem for reproducible GNSS PPP product resolution.

## Motivation

Lockfiles record the exact resolved products (URLs, hashes, sizes, local paths) for a single processing date. Goals:

1. **Reproducibility** — same `(task, date, version)` always yields the same products
2. **Cross-package sharing** — `pride-ppp` and future packages consume the same lockfiles
3. **Researcher sharing** — export a lockfile, import on another machine, relocate via WorkSpace
4. **Cloud batch cataloging** — lockfiles serve as manifests for batch runs

## Input / Output

### Identity Key

A lockfile is uniquely identified by `(task, date, version)`:
- **task**: from `DependencySpec.task` (e.g. `PPP`)
- **date**: processing date (datetime → `YYYY_DOY`)
- **version**: `gnss-ppp-products` package version via `importlib.metadata.version()`

Station is **not** part of the identity — lockfiles are station-independent.

### Inputs

| Name | Type | Source | Required | Notes |
|------|------|--------|----------|-------|
| dep_spec | `DependencySpec` | YAML config | Yes | Defines package, task, dependencies |
| date | `datetime` | Caller | Yes | Processing date (tz-aware) |
| local_sink_id | `str` | Caller | Yes | WorkSpace sink alias |
| version | `str` | `importlib.metadata` | Auto | Package version, not caller-supplied |
| strict | `bool` | Caller | No | Hash mismatch mode (default: `False` = warn) |

### Outputs

| Name | Type | Destination | Notes |
|------|------|-------------|-------|
| Per-file sidecar | `LockProduct` JSON | `<sink>_lock.json` next to product | Source of truth |
| Aggregate lockfile | `DependencyLockFile` JSON | `<lockfile_dir>/<name>_lock.json` | Auto-generated from sidecars |
| DependencyResolution | dataclass | In-memory | Returned to caller |

### Filename Convention

Old: `{station}_{package}_{task}_{YYYY}_{DOY}_{version}_lock.json`
New: `{package}_{task}_{YYYY}_{DOY}_{version}_lock.json`

Example: `PRIDE_PPP_2025_015_0.1.0_lock.json`

### Error Conditions

| Condition | Behavior | Caller Responsibility |
|-----------|----------|-----------------------|
| Lockfile exists for `(task, date, version)` | Skip resolution entirely, return cached resolution | None — transparent |
| Hash mismatch on import (strict=False) | Log warning, use product as-is | Review logs |
| Hash mismatch on import (strict=True) | Re-download product | Ensure network access |
| Corrupt/missing sidecar | Log warning, exclude from aggregate | None — graceful degradation |
| Sidecar references missing file | Exclude from aggregate, log warning | Re-resolve if needed |

## Performance

| Constraint | Target | Rationale |
|------------|--------|-----------|
| Concurrent resolvers | Safe — writes partitioned by date | Batch 365 days concurrently |
| Idempotency | Skip-if-exists (check lockfile before any work) | Avoid redundant FTP/HTTP |
| Retention | Keep all lockfiles indefinitely | Audit trail, reproducibility |
| TOCTOU race | Acceptable — concurrent same-date resolves are rare | Not worth file locking |
| Lockfile I/O | < 10ms per read/write | Small JSON files |

## API Surface

### Public Interface — `LockfileManager`

Single facade class in `lockfile/manager.py`. All callers go through this.

```python
class LockfileManager:
    def __init__(self, lockfile_dir: Path) -> None: ...

    # --- Query ---
    def exists(self, package: str, task: str, date: datetime, version: str) -> bool:
        """Check if a lockfile exists for the given identity."""

    def load(self, package: str, task: str, date: datetime, version: str) -> Optional[DependencyLockFile]:
        """Load an existing lockfile, or None."""

    # --- Write ---
    def save(self, lockfile: DependencyLockFile) -> Path:
        """Write/overwrite an aggregate lockfile."""

    def build_aggregate(self, products: List[LockProduct], package: str, task: str, date: datetime, version: str) -> DependencyLockFile:
        """Build a DependencyLockFile from a list of per-file sidecar LockProducts."""

    # --- Import/Export ---
    def export_lockfile(self, package: str, task: str, date: datetime, version: str) -> Path:
        """Package aggregate + sidecars for sharing."""

    def import_lockfile(self, path: Path, workspace: WorkSpace, strict: bool = False) -> DependencyLockFile:
        """Import a lockfile, relocate products via WorkSpace, handle hash mismatches."""

    # --- Naming ---
    @staticmethod
    def lockfile_name(package: str, task: str, date: datetime, version: str) -> str:
        """Canonical filename (no station)."""
```

### Internal (hidden)
- `_hash_file()` — utility, stays in `utilities/helpers.py`
- Per-file sidecar read/write — stays in `operations.py`, used by resolver internals
- Preference sorting, query expansion — stays in resolver

### Callers
- `DependencyResolver.resolve()` — checks `manager.exists()` for fast path, calls `manager.build_aggregate()` + `manager.save()` after resolution
- `PrideProcessor._resolve()` — receives lockfile path from resolver, stores in `ProcessingResult`
- Future CLI — uses `manager.export_lockfile()` / `manager.import_lockfile()`

### Configurable vs Hardcoded
- **Configurable**: `strict` mode (per-call), `lockfile_dir` (per-manager)
- **Hardcoded**: version source (`importlib.metadata`), filename convention, hash algorithm (SHA-256)

## Testability

### Key Scenarios
1. **Fresh resolve** → sidecars written → aggregate auto-generated, all fields populated
2. **Re-resolve same (task, date, version)** → `exists()` returns True, resolution skipped entirely
3. **Import with hash mismatch** → warns (default) or re-downloads (strict)
4. **Corrupt/missing sidecar** → aggregate handles gracefully, logs warning
5. **Lockfile round-trip** → write → read → validate matches original

### Test Boundaries
- All tests use local fixtures and mock resolvers — **no network access**
- `LockfileManager` tested with `tmp_path` directories
- `DependencyResolver` lockfile integration tested with pre-built fixture lockfiles
- Hash verification tested with known SHA-256 values

### Verification
- Round-trip: `load(save(lockfile)) == lockfile`
- Aggregate completeness: every sidecar product appears in aggregate
- Skip-if-exists: resolver returns without calling fetcher when lockfile present
- Import relocation: all `sink` paths updated to new WorkSpace locations

## Implementation Changes

### Models (`lockfile/models.py`)
- Remove `station` field from `DependencyLockFile`
- Change `version` default/description: package version, not format version

### Operations (`lockfile/operations.py`)
- Remove `station` parameter from `get_dependency_lockfile_name()`, `get_dependency_lockfile()`, `write_dependency_lockfile()`
- Add `HashMismatchMode` enum: `WARN`, `STRICT`
- Update `validate_lock_product()` to accept mode parameter

### New: Manager (`lockfile/manager.py`)
- `LockfileManager` class as described above

### Resolver (`factories/dependency_resolver.py`)
- Add skip-if-exists fast path at top of `resolve()`
- Remove `station` from `resolve()` signature
- Use `LockfileManager` instead of calling operations directly
- Auto-generate aggregate from collected sidecars after resolution
- Use `importlib.metadata.version()` for version

### PrideProcessor (`pride-ppp/src/pride_ppp/processor.py`)
- `_resolve()` returns `(DependencyResolution, Path)` — keep lockfile path
- Remove `station` parameter from resolve call

### Package init (`lockfile/__init__.py`)
- Export `LockfileManager`

## Open Questions
- None — all decisions resolved during interview.
