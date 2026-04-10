# `factories/` — Orchestration layer

This directory contains the classes that coordinate between the catalog layer
(resolved specs) and external I/O (FTP/HTTPS servers, local/cloud filesystem).

## Key classes

### `SearchPlanner` (`search_planner.py`)

Translates a product name + date + parameter constraints into a list of
`SearchTarget` objects — one per (product × version × variant × resource)
combination. It delegates to `ProductRegistry` for remote targets and
`WorkSpace` for local targets, both of which satisfy the `SourcePlanner`
protocol.

### `WormHole` (`remote_transport.py`)

Takes a `SearchTarget` list, groups targets by `(hostname, directory)`,
lists remote directories in parallel via `ConnectionPoolFactory`, and
matches filenames by regex. Returns expanded `SearchTarget` objects with
`filename.value` populated. Also handles single-file downloads.

### `ConnectionPoolFactory` (`connection_pool.py`)

Manages per-hostname `ConnectionPool` objects backed by
[fsspec](https://filesystem-spec.readthedocs.io/). Supports FTP, FTPS, HTTP,
HTTPS, and local file:// URIs. The pool semaphore enforces `max_connections`
per host — callers block rather than fail when the limit is reached.

### `SearchPlanner` + `WormHole` interaction

```
SearchPlanner.get(date, product, parameters)
    → List[SearchTarget]   (directory pattern + filename pattern)
WormHole.search(targets)
    → List[SearchTarget]   (filename.value populated from directory listing)
WormHole.download_one(target, ...)
    → Path                 (decompressed local file)
```

## Pipelines (`pipelines/`)

| Class | File | Responsibility |
|---|---|---|
| `DownloadPipeline` | `pipelines/download.py` | `FoundResource` → downloaded local path + sidecar lockfile |
| `LockfileWriter` | `pipelines/lockfile_writer.py` | `DependencyResolution` → aggregate `DependencyLockFile` |
| `ResolvePipeline` | `pipelines/resolve.py` | `DependencySpec` + date → `DependencyResolution` + lockfile path |

`ResolvePipeline` composes `ProductQuery` + `DownloadPipeline` +
`LockfileWriter`. It resolves all dependencies in parallel
(`ThreadPoolExecutor`, up to 15 workers) and writes the aggregate lockfile
only when all required dependencies are fulfilled.

## Supporting files

| File | Contents |
|---|---|
| `models.py` | `FoundResource`, `Resolution`, `DiscoveryEntry`, `DiscoveryReport`, `MissingProductError` |
| `ranking.py` | `sort_by_protocol`, `sort_by_preferences` — pure functions, no state |
| `source_planner.py` | `SourcePlanner` Protocol — implemented by `ProductRegistry` and `WorkSpace` |
