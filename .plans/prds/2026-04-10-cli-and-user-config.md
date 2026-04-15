# PRD: CLI Interface and User Configuration System

**Date:** 2026-04-10
**Status:** Draft
**Scope:** New `gnss-ppp-etl` package CLI and a shared `UserConfig` module

---

## Problem Statement

The `gnss-product-management` SDK and `pride-ppp` library are only usable today via Python scripts or
notebooks. Users who want to search for products, trigger a download, or run a PPP processing pipeline
must write Python code even for straightforward single-day tasks. There is also no mechanism to
persist user preferences (preferred analysis center, default product directory, max connections,
authentication credentials) across invocations; every call to `GNSSClient.from_defaults` accepts these
as constructor arguments that callers must re-specify every time.

This creates two related friction points:
1. **No CLI front-end.** Running a one-off product download or PPP job requires writing and maintaining
   a script rather than issuing a single terminal command.
2. **No persistent user configuration.** Preferred center priority lists, local product directories,
   authentication details, connection pool sizes, and processing defaults must be repeated in every
   script or hard-coded into examples.

The result is that new users face a steep onboarding curve, and experienced users duplicate boilerplate
across every project.

---

## Solution

Build two tightly coupled components:

1. **`UserConfig` module** — a machine-local (and optionally project-local) configuration layer that
   persists user preferences to a TOML file (`~/.config/gnss-ppp-etl/config.toml` by default, with
   project-level override via `./gnss-ppp-etl.toml`). The `UserConfig` is consumed by both the CLI and
   the Python SDK so that scripts can benefit from saved preferences without re-specifying them.

2. **`gnss` CLI** — a Typer-based command-line interface using Rich for output rendering. The CLI
   wraps the `GNSSClient` and `PrideProcessor` APIs in ergonomic subcommands for searching, downloading,
   resolving dependencies, and running PPP. It reads from `UserConfig` by default, with all options
   overridable at the command line.

Together these allow a user to:
```
# One-time setup
gnss config set base-dir ~/gnss_data
gnss config set center COD ESA GFZ   # preferred order

# Daily use — no more Python scripts
gnss search ORBIT --date 2025-01-15 --where TTT=FIN
gnss download ORBIT --date 2025-01-15
gnss resolve pride --date 2025-01-15
gnss ppp /data/rinex/NCC12540.25o
```

---

## User Stories

### Configuration

1. As a first-time user, I want to run `gnss config init` and be guided through setting my local
   product directory and preferred centers, so that subsequent commands work without extra flags.
2. As a user, I want to run `gnss config show` and see all current configuration values rendered in a
   readable table, so I know what defaults are active.
3. As a user, I want to run `gnss config set base-dir /path/to/dir` to change my local storage
   directory, so that all subsequent downloads go to the right place.
4. As a user, I want to run `gnss config set centers COD ESA GFZ` to set my preferred center ordering,
   so that searches and downloads use my preferred analysis centers first.
5. As a user, I want to run `gnss config set max-connections 6` to tune parallelism, so that I can
   speed up bulk downloads on fast networks.
6. As a user, I want the config file to live at a well-known path (`~/.config/gnss-ppp-etl/config.toml`)
   so I can version-control it or share it across machines.
7. As a user, I want to place a `gnss-ppp-etl.toml` in my project directory to override user-level
   defaults, so that different projects can use different centers or directories without changing global
   settings.
8. As a Python SDK user, I want to call `UserConfig.load()` and pass the result to `GNSSClient`, so that
   my scripts automatically reflect whatever the user has configured without hard-coded arguments.
9. As a user, I want to run `gnss config reset` to remove all saved settings and start from defaults,
   so I can recover from a bad configuration state.
10. As a user, I want environment variables (`GNSS_BASE_DIR`, `GNSS_CENTERS`, `GNSS_MAX_CONNECTIONS`)
    to override config file values, so that CI/CD pipelines can inject settings without modifying the
    config file.
11. As a user, I want to run `gnss config validate` and see whether my current configuration points to
    reachable directories and valid center IDs, so I can diagnose errors before running long jobs.

### Search

12. As a user, I want to run `gnss search ORBIT --date 2025-01-15` and see a Rich table of matching
    products (center, filename, server, URL), so that I can verify what is available before downloading.
13. As a user, I want to filter by product parameters (`--where TTT=FIN --where AAA=COD`) on the command
    line, so that I can narrow results without writing Python.
14. As a user, I want to specify a date range (`--date 2025-01-01 --to 2025-01-07`) and see all matching
    products for that window, so that I can plan a batch download.
15. As a user, I want search results to indicate whether a product is already cached locally, so I know
    which files I need to download.
16. As a user, I want to specify `--sources COD ESA` to restrict the search to a subset of centers, so
    that I can compare what different ACs have available.
17. As a user, I want to export search results as JSON (`--json results.json`) so that I can pipe them to
    other tools or scripts. The flag writes a structured JSON file to the given path rather than printing
    to stdout, consistent with the `--json PATH` convention already established in `dev/probe_catalog.py`.
18. As a user, I want to pass `--product version` or `--product variant` qualifiers, so that I can
    access non-default product format variants.

### Download

19. As a user, I want to run `gnss download ORBIT --date 2025-01-15` and have the product downloaded to
    my configured `base_dir`, so that I don't need to write a script.
20. As a user, I want a progress bar (Rich `Progress`) during download so that I can see how many files
    are in flight and estimate completion time.
21. As a user, I want failed downloads to be reported clearly in the terminal with the center and
    filename, so that I can manually retry or troubleshoot.
22. As a user, I want to specify `--dry-run` to preview what would be downloaded without actually
    fetching files, so that I can verify before committing.
23. As a user, I want to download multiple product types in one command (`gnss download ORBIT CLOCK ERP
    --date 2025-01-15`) so that I can stage a full product set quickly.
24. As a user, I want already-locally-cached files to be skipped automatically, so that re-running a
    download command is idempotent.

### Dependency Resolution

25. As a user, I want to run `gnss resolve <spec> --date 2025-01-15 --sink local` and have all required
    products for a dependency spec downloaded and a lockfile written, so that I can reproduce the product
    set later.
26. As a user, I want `gnss resolve` to print a summary table showing each dependency, its resolution
    status (local/downloaded/remote/missing), and the local path, so that I can verify the full product
    set is ready.
27. As a user, I want `gnss resolve --date-range 2025-01-01 2025-01-07` to resolve dependencies for an
    entire date range, so that I can stage a multi-day processing campaign.
28. As a user, I want to list the available named dependency specs (`gnss resolve --list`) so that I
    know what spec names I can use.
29. As a user, I want `--output lockfile.yaml` to write the resolution lockfile to a specified path, so
    that I can track exactly which files were used.

### PPP Processing

30. As a user, I want to run `gnss ppp /data/rinex/NCC12540.25o` to execute a full PRIDE-PPP-AR
    pipeline (product resolution + processing) from a single command, so that I don't need to write
    Python.
31. As a user, I want to specify `--mode final` or `--mode default` to select the dependency spec
    timeliness mode, so that I can choose between final product accuracy and near-real-time speed.
32. As a user, I want `gnss ppp` to print the WRMS position statistics after processing, so that I can
    quickly assess quality.
33. As a user, I want to pass `--output /data/output` to set where kinematic position and residual files
    are written, so that I don't need to configure the processor in Python.
34. As a user, I want to pass multiple RINEX files to `gnss ppp` and have them processed concurrently,
    so that campaign processing is fast.
35. As a user, I want `gnss ppp` to print a per-file summary table (site, date, WRMS, return code) when
    processing multiple files, so that I can see at a glance what succeeded or failed.
36. As a user, I want `--workers N` to control the concurrency of multi-file processing, so that I can
    tune load on my system.

### General / UX

37. As a user, I want all subcommands to support `--verbose` / `--quiet` flags that control log-level
    output, so that I can see debug details or suppress noise as needed.
38. As a user, I want `gnss --version` to print the package version, so that I can include it in bug
    reports.
39. As a user, I want `gnss --help` to show a short description of every subcommand, so that I can
    discover capabilities without reading the docs.
40. As a user, I want errors to be displayed using Rich's error panel (red, with detail) rather than
    raw Python tracebacks, so that the terminal output is readable.
41. As a user, I want the CLI to work on macOS, Linux, and Windows (WSL), so that the tool is usable
    across my team.
42. As a developer, I want the CLI layer to import `UserConfig` and convert it to `GNSSClient` kwargs,
    so that the SDK API is not coupled to CLI argument parsing.

---

## Implementation Decisions

### Module: `UserConfig`

A new module — likely housed in a new `gnss-cli` package or at the top-level `gnss-ppp-etl` package
— that owns reading, writing, and validating configuration. Backed by a TOML file.

**Resolution order (lowest to highest priority):**
1. Compiled defaults (shipped in code).
2. User-level config file: `~/.config/gnss-ppp-etl/config.toml`.
3. Project-level config file: `./gnss-ppp-etl.toml` (nearest ancestor).
4. Environment variables: `GNSS_BASE_DIR`, `GNSS_CENTERS`, `GNSS_MAX_CONNECTIONS`, `GNSS_LOG_LEVEL`.
5. Explicit CLI flags.

**Configuration fields (initial set):**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `base_dir` | `Path \| str \| None` | `None` | Local product storage root |
| `centers` | `list[str]` | `[]` (all) | Preferred center ordering |
| `max_connections` | `int` | `4` | Per-host connection pool size |
| `log_level` | `str` | `"WARNING"` | Logging level |
| `pride_dir` | `Path \| str \| None` | `None` | PRIDE-PPP working directory |
| `output_dir` | `Path \| str \| None` | `None` | Default PPP output directory |
| `default_mode` | `str` | `"default"` | Default `ProcessingMode` for PPP |

**Interface sketch:**
- `UserConfig.load(project_dir=None) -> UserConfig` — load from resolution chain.
- `UserConfig.save() -> None` — write to the user-level config file.
- `UserConfig.set(key, value) -> None` — update a field and persist.
- `UserConfig.to_client_kwargs() -> dict` — emit kwargs for `GNSSClient.from_defaults`.
- `UserConfig.to_processor_kwargs() -> dict` — emit kwargs for `PrideProcessor`.

`UserConfig` is a Pydantic `BaseSettings` model so that environment variable injection
is handled automatically and validation is strict.

### Module: `gnss` CLI (`typer` application)

A new `gnss` console script registered in `pyproject.toml`. Built with Typer and Rich.

**Subcommand tree:**

```
gnss
├── config
│   ├── init      — interactive first-run wizard
│   ├── show      — display all settings in a Rich table
│   ├── set       — set a single key/value
│   ├── reset     — remove user config file
│   └── validate  — check dirs exist, center IDs are known
├── search <PRODUCT>  — search for products; print Rich table
├── download <PRODUCTS...>  — download products; Rich progress bar
├── resolve <SPEC>    — resolve and download all dependencies; print summary
└── ppp <RINEX...>    — run PRIDE-PPP-AR pipeline
```

**Design constraints:**
- CLI commands never directly touch `GNSSClient` constructor args; they always call
  `UserConfig.load()` first and then call `UserConfig.to_client_kwargs()` to obtain kwargs.
  `GNSSClient` itself does not change.
- No new arguments are added to the existing `GNSSClient`, `PrideProcessor`, or `ProductQuery`
  APIs. The CLI is a pure consumer.
- Rich `Console` is injected into a shared `console` singleton; commands never print directly to
  `stdout`.
- All commands respect `--quiet` (suppresses Rich output, only errors) and `--verbose` (sets
  log level to DEBUG).

**Prior art — `dev/probe_catalog.py`:**

The existing `probe_catalog.py` dev tool establishes the Typer/Rich conventions that the production
CLI must follow consistently. All new CLI commands should adhere to these patterns:

- **Console singleton:** `console = Console()` defined at module level. All Rich output routes
  through this object — no `print()` calls and no ad-hoc `Console()` instances inside functions.
- **Progress factory:** A `_progress()` helper returns a `Progress` instance pre-configured with
  `SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn, TimeElapsedColumn, transient=True`.
  Reuse this factory (or a shared equivalent) rather than constructing ad-hoc progress bars.
- **`Annotated` options:** Every CLI option uses `Annotated[type, typer.Option("--flag", help="...")]`.
  Repeatable options use `list[str] | None` (where `None` means "all"). Boolean flags use `bool`
  with `typer.Option("--flag/--no-flag")`.
- **Status enums:** Each command group defines result states as a `str, Enum` subclass
  (e.g., `ConnStatus`, `SearchStatus`). This keeps Rich markup dicts type-safe.
- **Result dataclasses:** Each command's probe/check operation produces a typed `@dataclass`
  (e.g., `ConnResult`, `ProbeResult`) rather than raw dicts. Structured output enables `--json`.
- **Concurrent execution:** Network-bound operations use `ThreadPoolExecutor(max_workers=workers)
  + as_completed(futures)` with live progress bar updates inside the `as_completed` loop.
- **`--json PATH` flag:** Every command that produces tabular results accepts a `--json PATH`
  option that writes structured results to disk. The flag name is `--json` with a `Path | None`
  type, not `--output` with a format string.
- **`--workers N` flag:** Every command making parallel network calls exposes
  `Annotated[int, typer.Option("--workers", help="...")]` with a sensible default (e.g., `8`).
- **Rich markup dicts:** Status-to-color mappings are defined as module-level dicts
  (`_CONN_MARKUP`, `_SEARCH_MARKUP`); commands look up markup by enum value rather than
  branching inline.
- **Summary panel:** Each command ends by printing a `Panel(...)` summary via a small helper
  function `_summary(ok, total, extra, elapsed, title)`. Color is green when all checks pass,
  red otherwise.
- **Mode dispatch:** Commands with optional modes (e.g., connectivity vs. product search in
  `probe_catalog.py`) dispatch based on the *presence or absence* of optional arguments, not via
  separate sub-subcommands. Use runtime conditions, not extra nesting.
- **Exit codes:** `raise typer.Exit(1)` when any check fails; `raise typer.Exit(0)` (or fall
  through) on full success. Never swallow failures silently.
- **`gnss config validate` specifics:** This command should use `ConnectionPoolFactory` directly
  (as `check_server()` does in `probe_catalog.py`) rather than routing through `GNSSClient`.
  Connectivity validation is a pre-client operation and must work even when `base_dir` is
  unconfigured.

### Packaging

The CLI and `UserConfig` may be added to the monorepo root `gnss-ppp-etl` package (which is
today a thin orchestration package) or extracted to a new `packages/gnss-cli/` package.
Given that the root package already depends on both `gnss-product-management` and `pride-ppp`,
embedding in the root package is the simpler initial choice. A separate `gnss-cli` package
can be extracted later if users want the CLI without the PPP dependency.

`typer` and `rich` are already present in the `dev` dependency group; they must be promoted to
regular dependencies of whichever package owns the CLI.

The console script entry point:
```toml
[project.scripts]
gnss = "gnss_ppp_etl.cli.app:main"
```

### Config file format

TOML is chosen for human-editability and native Python 3.11+ support (`tomllib` / `tomli` backport).
A generated `config.toml` will include inline comments for every field.

---

## Testing Decisions

**What makes a good test here:** test external behavior (what the user sees or what files/state are
produced) not internal wiring. For the CLI, that means invoking commands via Typer's test runner and
asserting on exit code, stdout content, and filesystem side effects. For `UserConfig`, that means
asserting on the resolved value of fields under different combinations of config file + env vars.

**Modules to test:**

| Module | Test focus | Prior art |
|--------|-----------|-----------|
| `UserConfig` | Resolution order: default → user file → project file → env var; Pydantic validation errors; `to_client_kwargs` produces correct kwargs | `test_product_environment.py` (Pydantic model construction) |
| `gnss config` subcommands | `init` writes a valid TOML; `show` renders a table; `set` updates a key; `reset` removes the file; `validate` passes/fails correctly | — |
| `gnss search` | Returns non-zero exit on unknown product; renders table columns correctly; `--json file` produces parseable JSON | — |
| `gnss download` | Downloads the correct file to `base_dir`; skips cached files; `--dry-run` produces no filesystem side effects | — |
| `gnss resolve` | Calls `ResolvePipeline` with correct spec and date; writes lockfile; handles missing products gracefully | — |
| `gnss ppp` | Passes RINEX paths to `PrideProcessor`; renders summary table; exits non-zero on processor failure | — |

Tests for `gnss download`, `gnss resolve`, and `gnss ppp` that touch live servers are marked
`@pytest.mark.integration` and excluded from the standard CI run (in line with existing convention in
`packages/gnss-product-management/test/`).

**CLI test conventions (from `probe_catalog.py` prior art):**
- Invoke commands through Typer's `CliRunner` (`from typer.testing import CliRunner`).
- Capture Rich output with `Console(force_terminal=True, file=string_io)` where terminal color
  codes need to be asserted, or strip ANSI codes for plain-text assertions.
- Assert on `result.exit_code`, `result.output` substrings, and filesystem side effects.
- Unit tests mock `ConnectionPoolFactory` and `GNSSClient` to avoid live network calls.
- Integration tests may call `probe_catalog.py`'s own helpers (e.g., `_unique_servers()`,
  `check_server()`) as validated reference implementations.

---

## Out of Scope

- Authentication management (storing `.netrc` or NASA Earthdata credentials). The CLI will document
  that CDDIS requires a `.netrc` entry but will not write or manage credentials itself.
- A graphical or web UI.
- Real-time product streaming.
- Output format conversions (SP3 → other formats, CLK → other formats).
- Automated scheduling/cron integration.
- Windows native (non-WSL) path handling beyond what `pathlib` provides.
- Publishing the `gnss` CLI to PyPI in this iteration (it will be installable from the monorepo only).

---

## Further Notes

- `pydantic-settings` (`BaseSettings`) should be evaluated for `UserConfig` to get environment
  variable injection for free; it is already in the transitive dependency graph via Pydantic v2.
- The `gnss config init` wizard should use Rich `Prompt.ask` so that the interactive path is
  testable and not raw `input()` calls.
- The `gnss search` table should use Rich `Table` with sortable columns. Consider a `--sort` flag
  in a follow-up.
- The Rich `Progress` bar during downloads should report both file count and byte count where the
  file size is known from the server `Content-Length` header.
- `gnss resolve --date-range` implies looping `GNSSClient.resolve_dependencies`; ensure the lockfile
  output format can represent multi-day results (e.g., one lockfile per date, or a combined manifest).
- The project-level config override (`./gnss-ppp-etl.toml`) walks up the filesystem from `cwd`
  (similar to how `pyproject.toml` is discovered by tools), stopping at the user's home directory or
  a filesystem boundary. This makes CI pipelines and Docker containers predictable.
- A `gnss doctor` subcommand (out of scope for v1 but noted) could verify the PRIDE-PPP-AR binary is
  installed and reachable, and confirm network connectivity to each configured center.
