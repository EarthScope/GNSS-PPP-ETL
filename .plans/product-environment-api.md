# Plan: ProductEnvironment Public API

> Source PRD: `.plans/prds/2026-03-21-product-environment-public-api.md`

## Architectural decisions

Durable decisions that apply across all phases:

- **Single entry point**: `ProductEnvironment` is the sole public class. All operations are methods on it.
- **Construction**: `ProductEnvironment(workspace="/path")` or `ProductEnvironment(workspace=("/path", "alias"))`. Only argument is workspace.
- **Immutability**: Environment is frozen after `__init__`. No mutation methods.
- **Universal specs**: Parameter catalog, format catalog, product catalog, and local folder spec are bundled YAML configs auto-loaded at construction. Never caller-provided.
- **Return types**: All public methods return Pydantic models: `FoundResource`, `ClassifiedProduct`, `Resolution`, `DiscoveryReport`.
- **Filters**: `dict[str, str]` mapping parameter names to values, applied at query level.
- **Error model**: `MissingProductError` raised when required products cannot be found. `FileNotFoundError` for invalid workspace path. `ValueError` for unknown product names.
- **Internal delegation**: Public methods delegate to existing `QueryFactory`, `ResourceFetcher`, `DependencyResolver`, `LocalResourceFactory`, `RemoteResourceFactory`. Internals are not changed, only wrapped.

---

## Phase 1: Environment Construction + classify()

**User stories**: 1, 6, 13, 14, 15, 16, 22, 23

### What to build

A new `ProductEnvironment` constructor that takes only a `workspace` argument (str or tuple), auto-loads all bundled YAML specs, registers all centers and dependency specs, validates the base_dir exists, defaults the alias from the path stem, and validates that every product has a sink path in the local spec. Remove `register_remote()`, `register_dependency_spec()`, and the `local_factory` setter to enforce immutability.

Define the `FoundResource`, `ClassifiedProduct`, `Resolution`, `DiscoveryReport` Pydantic return-type models and `MissingProductError` exception.

Implement `classify(filename)` which pattern-matches a filename against all known product format templates and returns a `ClassifiedProduct` with the product name, center, quality, date, and full parameter dict. Raises `ValueError` for unrecognized filenames.

### Acceptance criteria

- [ ] `ProductEnvironment(workspace="/tmp/existing-dir")` succeeds, loads all catalogs and centers
- [ ] `ProductEnvironment(workspace="/tmp/nonexistent")` raises `FileNotFoundError`
- [ ] `ProductEnvironment(workspace="/tmp/mydir")` defaults alias to `"mydir"`
- [ ] `ProductEnvironment(workspace=("/tmp/mydir", "campaign-A"))` sets alias to `"campaign-A"`
- [ ] No `register_remote`, `register_dependency_spec`, or `local_factory` setter on the environment
- [ ] `env.classify("WUM0MGXFIN_20250150000_01D_05M_ORB.SP3.gz")` returns `ClassifiedProduct` with product="ORBIT", center="WUM"
- [ ] `env.classify("garbage.txt")` raises `ValueError`
- [ ] All existing tests still pass (no regressions from constructor refactor)

---

## Phase 2: find() — local search

**User stories**: 2, 3, 10, 11, 12, 19, 20, 21

### What to build

Implement `env.find(product, date, *, centers=None, filters=None, all=False)`. In this phase, only the local search path is wired — the method queries the workspace for matching files using `QueryFactory` and `ResourceFetcher` against the local factory only.

Returns a single best `FoundResource` by default (ranked by quality preference from config), or a ranked `list[FoundResource]` when `all=True`. The `filters` dict narrows parameters at the query level. The `centers` parameter is accepted but only affects remote (wired in Phase 3).

### Acceptance criteria

- [ ] `env.find(product="ORBIT", date=date(2025, 1, 15))` returns a `FoundResource` when a matching file exists locally
- [ ] `env.find(product="ORBIT", date=date(2025, 1, 15))` returns `None` when no local match exists (remote not yet wired)
- [ ] `env.find(..., all=True)` returns `list[FoundResource]` ranked by quality preference
- [ ] `env.find(..., filters={"TTT": "FIN"})` narrows to only FIN-quality matches
- [ ] `env.find(product="UNKNOWN", ...)` raises `ValueError`
- [ ] Result `FoundResource` has correct product name, source type "local", and path

---

## Phase 3: find() — remote search + download()

**User stories**: 2, 3, 4, 5

### What to build

Extend `find()` to fall through to remote center search when local miss. The `centers` parameter now filters which remote centers to query. Remote results are ranked below local results.

Implement `env.download(resource)` which fetches a remote `FoundResource` to the workspace using the local folder spec for destination path. Accepts a single resource or a list. Returns `Path` or `list[Path]`. No-op for already-local resources (returns existing path).

### Acceptance criteria

- [ ] `env.find(product="ORBIT", date=..., centers=["wum"])` searches only the WUM remote center after local miss
- [ ] `env.find(...)` with no `centers` arg searches all registered centers
- [ ] Local results rank above remote results in the returned list
- [ ] `env.download(remote_resource)` fetches the file and returns a `Path` in the workspace
- [ ] `env.download(local_resource)` returns the existing local path without re-downloading
- [ ] `env.download([res1, res2])` returns `list[Path]`

---

## Phase 4: resolve()

**User stories**: 7, 8, 17, 18

### What to build

Implement `env.resolve(task, date, *, centers=None, filters=None)`. Delegates to `DependencyResolver` internally: walks the dependency graph for the named task, calls `find()` + `download()` for each required product, produces a `ProductLockfile`, and returns a `Resolution` containing the lockfile and all local paths.

Raises `MissingProductError` if any required dependency cannot be found. Wire lockfile-as-input: `env.download(lockfile)` accepts a `ProductLockfile` and downloads + hash-validates each entry.

### Acceptance criteria

- [ ] `env.resolve(task="pride-pppar", date=date(2025, 1, 15))` returns `Resolution` with paths and lockfile
- [ ] `env.resolve(task="pride-pppar", ...)` raises `MissingProductError` when a required dep is unavailable
- [ ] `env.resolve(task="unknown-task", ...)` raises `KeyError`
- [ ] Returned `Resolution.lockfile` is a valid `ProductLockfile` with entries for each resolved product
- [ ] `env.resolve(..., filters={"TTT": "FIN"})` applies filters to all dependency queries
- [ ] `env.download(lockfile)` downloads each entry and validates hashes

---

## Phase 5: discover()

**User stories**: 9

### What to build

Implement `env.discover(date, *, centers=None, filters=None, products=None)`. Runs `find(..., all=True)` across all (or specified) products without downloading. Returns a `DiscoveryReport` — a structured summary showing what's available per product, per center, per quality tier.

### Acceptance criteria

- [ ] `env.discover(date=date(2025, 1, 15))` returns a `DiscoveryReport` covering all 16 products
- [ ] `env.discover(..., products=["ORBIT", "CLOCK"])` limits to those two products
- [ ] `env.discover(..., centers=["wum"])` limits to WUM center
- [ ] Report includes product name, center, quality, and source type (local/remote) for each match
- [ ] No files are downloaded
