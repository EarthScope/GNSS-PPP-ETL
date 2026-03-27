"""
Dependency resolver — resolve a DependencySpec via QueryFactory.

Two-phase resolution:
  1. **Local** — check ``base_dir`` for files already on disk.
  2. **Remote** — use :class:`ResourceFetcher` to search/download.

Preferences are applied by sorting ``ResourceQuery`` results according
to the ``SearchPreference.parameter`` / ``sorting`` cascade defined in
the dependency spec.
"""

from __future__ import annotations

from collections import defaultdict
import datetime
import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, thread
from functools import partial
import threading
    
from gnss_ppp_products.factories.environment import ProductEnvironment
from gnss_ppp_products.specifications.dependencies.lockfile import LockProduct
from gnss_ppp_products.specifications.parameters.parameter import Parameter
from gnss_ppp_products.specifications.products.catalog import ProductCatalog
from gnss_ppp_products.specifications.remote.resource import ResourceQuery
from gnss_ppp_products.specifications.dependencies.dependencies import (
    Dependency,
    DependencyResolution,
    DependencySpec,
    ResolvedDependency,
    SearchPreference,
)
from gnss_ppp_products.factories.query_factory import QueryFactory
from gnss_ppp_products.factories.resource_fetcher import ResourceFetcher, FetchResult
from gnss_ppp_products.specifications.products.product import ProductPath, infer_from_regex
from .workspace import WorkSpace

logger = logging.getLogger(__name__)


def _get_param_value(rq: ResourceQuery, param_name: str) -> str:
    """Extract a parameter value from a ResourceQuery's product."""
    for p in rq.product.parameters:
        if p.name == param_name and p.value is not None:
            return p.value
    return ""


def _build_remote_url(rq: ResourceQuery) -> str:
    """Construct a full remote URL from a ResourceQuery."""
    protocol = (rq.server.protocol or "").lower()
    hostname = rq.server.hostname
    directory = rq.directory.value or rq.directory.pattern
    filename = ""
    if rq.product.filename:
        filename = rq.product.filename.value or rq.product.filename.pattern
    sep = "" if directory.startswith("/") else "/"
    trail = "" if directory.endswith("/") else "/"
    hostname = hostname.split("//")[-1]  # Remove any existing protocol prefix
    return f"{protocol}://{hostname}{sep}{directory}{trail}{filename}"


def _file_pattern(rq: ResourceQuery) -> str:
    """Return the filename regex pattern from a ResourceQuery."""
    if rq.product.filename:
        return rq.product.filename.value or rq.product.filename.pattern
    return ""


def _hash_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


class DependencyResolver:
    """Resolve a :class:`DependencySpec` using :class:`QueryFactory`.

    Parameters
    ----------
    dep_spec
        The dependency specification to resolve.
    base_dir
        Root directory for local product storage.
    query_factory
        A :class:`QueryFactory` wired to the desired centres.
    fetcher
        Optional :class:`ResourceFetcher` for remote search/download.
        When *None*, only local resolution is attempted.
    """

    def __init__(
        self,
        dep_spec: DependencySpec,
        query_factory: QueryFactory,
        product_environment: ProductEnvironment,
        fetcher: ResourceFetcher,
    ) -> None:
        self.dep_spec = dep_spec
        self._qf: QueryFactory = query_factory
        self._fetcher = fetcher
        self._product_environment = product_environment


    def resolve(
        self,
        date: datetime.datetime,
        local_sink_id: str,
       
    ) -> DependencyResolution:
        """Resolve every dependency in the spec for *date*.

        Parameters
        ----------
        date
            Target date (timezone-aware datetime).
        download
            If *True* and a remote match is found, download it.
        """
        results: List[ResolvedDependency] = []

        # Pre-warm: probe connectivity for all unique remote servers so
        # that per-dependency threads don't duplicate slow connection checks.
        # all_queries: List[ResourceQuery] = []
        # for dep in self.dep_spec.dependencies:
        #     try:
        #         qs = self._qf.get(
        #             date,
        #             product={"name": dep.spec},
        #             parameters=dep.constraints or None,
        #         )
        #         all_queries.extend(qs)
        #     except (ValueError, KeyError):
        #         pass
        # if all_queries:
        #     self._fetcher.warm_connectivity_cache(all_queries)

        partial_resolve_one = partial(
            self._resolve_one,
            date=date,
            local_sink_id=local_sink_id,
        )
        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = [executor.submit(partial_resolve_one, dep) for dep in self.dep_spec.dependencies]
            for future in futures:
                resolved = future.result()
                if resolved:
                    results.append(resolved)

        resolution = DependencyResolution(
            spec_name=self.dep_spec.name,
            resolved=results,
        )
        logger.info(resolution.summary())
        return resolution

    # ---- internal helpers ------------------------------------------

    def _resolve_one(
        self,
        dep: Dependency,
        date: datetime.datetime,
        local_sink_id: str,
    ) -> Optional[ResolvedDependency]:
        """Resolve a single dependency."""
        try:
            queries = self._qf.get(
                date,
                product={"name": dep.spec},
                parameters=dep.constraints or None,
            )
            with threading.Lock():
                self._fetcher.warm_connectivity_cache(queries)
        except (ValueError, KeyError) as exc:
            logger.debug("No queries for %s: %s", dep.spec, exc)
            return ResolvedDependency(
                spec=dep.spec, required=dep.required, status="missing",
            )

        if not queries:
            logger.warning(f"No queries returned for dependency {dep.spec} with constraints {dep.constraints}")
            return ResolvedDependency(
                spec=dep.spec, required=dep.required, status="missing",
            )

        queries = self._sort_by_preferences(queries)

        # Fetch the queries.
        logger.info(f"Searching for {len(queries)} queries for dependency {dep.spec}...")
        fetched_queries: List[FetchResult] = self._fetcher.search(queries)
        logger.info(f"Fetched {len(fetched_queries)} queries for dependency {dep.spec}")

        # Expand the fetched queries into a list of resource queries.
        expanded_queries: List[ResourceQuery] = self._expand_fetch_results(fetched_queries)


        expanded_queries = self._sort_by_preferences(expanded_queries)
        filename_groups = defaultdict(list)
        for rq in expanded_queries:
            filename_groups[rq.product.filename.value].append(rq)

        # sort by server protocol
        for key, group in filename_groups.items():
            filename_groups[key] = self._sort_by_protocol(group)

        for rq_index in expanded_queries:
            for rq in filename_groups[rq_index.product.filename.value]:
                if (rq.server.protocol or "").upper() in ("FILE", "LOCAL", ""):
                    resolved = self._resolve_local(
                        rq=rq, dep=dep, local_sink_id=local_sink_id, local_resource_factory=self._qf._local, date=date)
                    if resolved is not None:
                        return resolved

                else:

                    resolved = self._resolve_remote(
                        rq=rq, dep=dep, local_sink_id=local_sink_id, local_resource_factory=self._qf._local, date=date,
                    )
                    if resolved is not None:
                        return resolved

    def _expand_fetch_results(self, fetched: List[FetchResult]) -> List[ResourceQuery]:
        """Expand FetchResults into ResourceQueries with filename values filled in."""
        expanded: List[ResourceQuery] = []
        for fq in fetched:
            if fq.error:
                continue
            assert fq.query.directory.value is not None, "Fetched query must have directory value filled in"
            assert fq.query.product.filename is not None, "Fetched query must have filename value filled in"  # type: ignore
            if not fq.matched_filenames:
                logger.info(f"No matches found for query {fq.query.product.filename.pattern}")
                continue
            for filename in fq.matched_filenames:
                # Create a new ResourceQuery with the filename value filled in.
                rq = fq.query.model_copy(deep=True)
                rq.product.filename.value = filename
                rq = self._update_parameters(rq)
                expanded.append(rq)
        return expanded
    
    def _sort_by_preferences(
        self,
        queries: List[ResourceQuery],
    ) -> List[ResourceQuery]:
        """Sort queries according to the preference cascade."""
        if not self.dep_spec.preferences:
            return queries

        for pref in reversed(self.dep_spec.preferences):
            param_name = pref.parameter
            sorting = [v.upper() for v in pref.sorting]

            def _key(rq: ResourceQuery, _pn=param_name, _s=sorting) -> int:
                try:
                    val = _get_param_value(rq, _pn).upper()
                    return _s.index(val)
                except (ValueError, TypeError):
                    return len(_s)

            queries = sorted(queries, key=_key)

        return queries

    def _sort_by_protocol(self, queries: List[ResourceQuery]) -> List[ResourceQuery]:
        """Sort queries by server protocol, preferring local/file over remote."""
        protocol_sort_order = ["FILE", "LOCAL", "FTP", "FTPS", "HTTP", "HTTPS"]
        return sorted(
            queries,
            key=lambda rq: protocol_sort_order.index((rq.server.protocol or "").upper()) if (rq.server.protocol or "").upper() in protocol_sort_order else len(protocol_sort_order)
        )

    def _update_parameters(self,resource_query: ResourceQuery) -> ResourceQuery:
        """Update a ResourceQuery's parameters by re-interpolating its directory and filename patterns."""
        updated = resource_query.model_copy(deep=True)
        updated_params: List[Parameter] = infer_from_regex(
            regex=updated.product.filename.pattern,  # type: ignore
            filename=updated.product.filename.value,  # type: ignore
            parameters=updated.product.parameters,
        )
        updated.product.parameters = updated_params
        classification_results = self._product_environment.classify(filename=updated.product.filename.value, parameters=updated.product.parameters)
        if classification_results:
            class_parameters:Dict[str,str] = classification_results.get("parameters", {}) # TODO make the classification results more structured so we don't have to do this stringly-typed dance
            for p in updated.product.parameters:
                if p.name in class_parameters and p.value is None:
                    p.value = class_parameters[p.name]

        return updated

    def _resolve_remote(
            self,
            rq: ResourceQuery,
            dep: Dependency,
            local_sink_id: str,
            local_resource_factory:LocalResourceFactory,
            date: datetime.datetime,

    ) -> Optional[ResolvedDependency]:

        assert rq.product.filename.value is not None, "Remote resolution requires filename to be filled in"

        # local_path = self._download_result(rq, dest_dir)
        local_path: Optional[Path] = self._fetcher.download_one(
            query=rq,
            local_resource_id=local_sink_id,
            local_factory=local_resource_factory,
            date = date,
        )
        if local_path is None:
            return None
        file_hash = _hash_file(local_path)
        file_size = local_path.stat().st_size
        resolved = self._make_resolved(
            dep, rq,
            status="downloaded",
            local_path=local_path,
            file_hash=file_hash,
            file_size=file_size,
            check_existing_lock=False,
        )
        lock_dir = local_resource_factory.lockfile_dir(local_sink_id, date)
        self._write_file_lock(local_path, resolved, lock_dir=lock_dir)
        return resolved

    def _resolve_local(
            self,
            rq: ResourceQuery,
            dep: Dependency,
            local_sink_id: str,
            local_resource_factory:LocalResourceFactory,
            date: datetime.datetime,

    ) -> Optional[ResolvedDependency]:

        source_directory = Path(rq.server.hostname) / rq.directory.value
        assert source_directory.exists() and source_directory.is_dir(), f"Local directory {source_directory} does not exist for query {rq}"
        filename = rq.product.filename.value
        assert filename is not None, f"Local resolution requires filename to be filled in for query {rq}"

        source_path = source_directory / filename

        # If the file is not present in the local_sink resource, we can copy it there.
        sink_query = local_resource_factory.sink_product(rq.product, local_sink_id, date)
        sink_directory = Path(sink_query.server.hostname) / sink_query.directory.value
        assert sink_directory is not None, "Sink product must have a directory value"
        if not sink_directory == source_directory:
            sink_directory.mkdir(parents=True, exist_ok=True)
            # Copy the file to the sink directory
            dest_path = sink_directory / filename
            if not dest_path.exists():
                dest_path.write_bytes(source_path.read_bytes())
                logger.info(f"Copied local file {source_path} to sink directory {dest_path}")
            source_path = dest_path

        # Try to reuse hash from an existing lockfile to avoid re-hashing
        lock_dir = local_resource_factory.lockfile_dir(local_sink_id, date)
        existing_lock = self._get_file_lock(source_path, lock_dir=lock_dir)
        if existing_lock and existing_lock.hash and existing_lock.size == source_path.stat().st_size:
            file_hash = existing_lock.hash
            file_size = existing_lock.size
        else:
            file_hash = _hash_file(source_path)
            file_size = source_path.stat().st_size

        resolved = self._make_resolved(
            dep, rq,
            status="local",
            local_path=source_path,
            file_hash=file_hash,
            file_size=file_size,
            check_existing_lock=False,
            existing_lock=existing_lock,
        )
        # Write/update the lockfile if it didn't exist or hash changed
        if not existing_lock or existing_lock.hash != file_hash:
            self._write_file_lock(source_path, resolved, lock_dir=lock_dir)
        return resolved

    @staticmethod
    def _get_file_lock(local_path: Path, *, lock_dir: Optional[Path] = None) -> Optional[LockProduct]:
        """Load an existing ``<filename>.lock`` sidecar.

        Checks *lock_dir* first (the dedicated lockfiles directory), then
        falls back to the file's own parent directory for backwards
        compatibility.
        """
        name = f"{local_path.name}.lock"
        candidates = []
        if lock_dir is not None:
            candidates.append(lock_dir / name)
        candidates.append(local_path.parent / name)
        for lock_path in candidates:
            if lock_path.exists() and lock_path.is_file():
                try:
                    with open(lock_path, 'r') as f:
                        lock_data = json.load(f)
                    return LockProduct.model_validate(lock_data)
                except Exception:
                    logger.debug("Failed to read lockfile %s", lock_path)
        return None

    @staticmethod
    def _write_file_lock(
        local_path: Path,
        resolved: ResolvedDependency,
        *,
        lock_dir: Optional[Path] = None,
    ) -> None:
        """Write a ``<filename>.lock`` JSON sidecar into *lock_dir*.

        Falls back to the file's parent directory when *lock_dir* is None.
        """
        if resolved.lockfile is None:
            return
        target = lock_dir if lock_dir is not None else local_path.parent
        target.mkdir(parents=True, exist_ok=True)
        lock_path = target / f"{local_path.name}.lock"
        lock_data = json.loads(resolved.lockfile.model_dump_json())
        lock_data["local_path"] = str(local_path)
        lock_path.write_text(json.dumps(lock_data, indent=2), encoding="utf-8")
        logger.info("Wrote lockfile %s", lock_path)

    @staticmethod
    def _make_resolved(
        dep: Dependency,
        rq: ResourceQuery,
        *,
        status: str,
        local_path: Optional[Path],
        file_hash: str = "",
        file_size: int | None = None,
        check_existing_lock: bool = True,
        existing_lock: Optional[LockProduct] = None,
    ) -> ResolvedDependency:
        """Build a :class:`ResolvedDependency` from a ResourceQuery."""
        from gnss_ppp_products.specifications.dependencies.lockfile import LockProduct

        remote_url = _build_remote_url(rq)
        regex = _file_pattern(rq)

        lock_product: Optional[LockProduct] = existing_lock
        if lock_product is None and check_existing_lock and local_path is not None:
            lock_product = DependencyResolver._get_file_lock(local_path)
        if not lock_product:
            lock_product = LockProduct(
                name=dep.spec,
                description=dep.description or "",
                required=dep.required,
                url=remote_url,
                regex=regex,
                hash=file_hash,
                size=file_size,
                local_directory=str(local_path.parent) if local_path else "",
            )

        return ResolvedDependency(
            spec=dep.spec,
            required=dep.required,
            status=status,
            remote_url=remote_url,
            local_path=local_path,
            hash=file_hash,
            size=file_size,
            description=dep.description,
            lockfile=lock_product,
        )
