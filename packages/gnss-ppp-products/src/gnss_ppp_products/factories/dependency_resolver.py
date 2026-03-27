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

from ast import Tuple
from collections import defaultdict
import datetime
import hashlib
import json
import logging
from os import write
import re
from pathlib import Path
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, thread
from functools import partial
import threading
    
from anyio import Lock
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

from .lockfile_manager import (
    LockProduct, validate_lock_product,build_lock_product,get_lock_product_path,get_lock_product,write_lock_product,DependecyLockFile,
    get_dependency_lockfile_name,get_dependency_lockfile,write_dependency_lockfile
)
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
        station: Optional[str] = None,
        version: Optional[str] = "0",
       
    ) -> Tuple[DependencyResolution, Optional[Path]]:
        """Resolve every dependency in the spec for *date*.

        Parameters
        ----------
        date
            Target date (timezone-aware datetime).
        download
            If *True* and a remote match is found, download it.
        """
        '''
        steps:
        1. Check for existing dependency lockfile for this spec/date/station. If found, validate each lock product and add valid ones to results, removing them from the to_resolve list.
        2. For each remaining dependency in to_resolve, call _resolve_one in parallel
        3. Aggregate results into a DependencyResolution and return.
        
        
        
        '''
        results: List[ResolvedDependency] = []
        lockfiles: List[LockProduct] = []
        to_resolve = self.dep_spec.dependencies

        dep_lockfile_info: Tuple[Optional[DependecyLockFile], Optional[Path]] = get_dependency_lockfile(
            directory=self._qf._local.lockfile_dir(local_sink_id),
            station=station,
            package=self.dep_spec.package,
            task=self.dep_spec.task,
            version=version,
            date=date,
        )
        dep_lock_file, dep_lock_file_path = dep_lockfile_info
   
        if dep_lock_file:
            logger.info(f"Found existing lockfile for {self.dep_spec.name} on {date.date()}: {dep_lock_file}")
            for lock_product in dep_lock_file.products:
                dep_spec = next((d for d in self.dep_spec.dependencies if d.spec == lock_product.name), None)
                if dep_spec and validate_lock_product(lock_product):
                    # Remove this product from the to_resolve list since it's already resolved in the lockfile
                    to_resolve = [dep for dep in to_resolve if dep.spec != lock_product.name]

                    resolved = ResolvedDependency(
                        spec=lock_product.name,
                        required=dep_spec.required,
                        status="local",
                        remote_url=lock_product.url,
                        local_path=Path(lock_product.sink),
                        hash=lock_product.hash,
                        size=lock_product.size,
                        description=dep_spec.description,
                        lockfile=lock_product,
                    )
                    results.append(resolved)
                else:
                    logger.warning(f"Invalid lock product in lockfile {dep_lock_file}: {lock_product}. Will attempt to re-resolve.")
        
        else:
            dep_lock_file = DependecyLockFile(
                station=station or "",
                package=self.dep_spec.package,
                task=self.dep_spec.task,
                date=date.strftime("%Y-%m-%d"),
                products=[],
            )
        partial_resolve_one = partial(
            self._resolve_one,
            date=date,
            local_sink_id=local_sink_id,
        )
        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = [executor.submit(partial_resolve_one, dep) for dep in to_resolve]
            for future in futures:
                resolved, lock_file = future.result()
                if resolved and lock_file:
                    results.append(resolved)
                    lockfiles.append(lock_file)

        if lockfiles:
            dep_lock_file.products.extend(lockfiles)
            write_dependency_lockfile(
                lockfile=dep_lock_file,
                directory=dep_lock_file_path.parent,
                update=True
            )
        resolution = DependencyResolution(
            spec_name=self.dep_spec.name,
            resolved=results,
        )
        logger.info(resolution.summary())
        return resolution,dep_lock_file_path

    # ---- internal helpers ------------------------------------------

    def _resolve_one(
        self,
        dep: Dependency,
        date: datetime.datetime,
        local_sink_id: str,
    ) -> Tuple[Optional[ResolvedDependency], Optional[LockProduct]]:
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
            ), None

        if not queries:
            logger.warning(f"No queries returned for dependency {dep.spec} with constraints {dep.constraints}")
            return ResolvedDependency(
                spec=dep.spec, required=dep.required, status="missing",
            ), None

        queries = self._sort_by_preferences(queries)

        # Fetch the queries.
        logger.info(f"Searching for {len(queries)} queries for dependency {dep.spec}...")
        fetched_queries: List[FetchResult] = self._fetcher.search(queries)
        if not fetched_queries:
            logger.warning(f"No fetch results for dependency {dep.spec}")
            return ResolvedDependency(
                spec=dep.spec, required=dep.required, status="missing",
            ), None
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
            remote_urls = [_build_remote_url(rq) for rq in filename_groups[rq_index.product.filename.value] if (rq.server.protocol or "").upper() not in ("FILE", "LOCAL", "")]
            for rq in filename_groups[rq_index.product.filename.value]:
                if (rq.server.protocol or "").upper() in ("FILE", "LOCAL", ""):
                    resolved, lock_file = self._resolve_local(
                        rq=rq, dep=dep, local_sink_id=local_sink_id, local_resource_factory=self._qf._local, date=date, alternative_urls=remote_urls)
                    if resolved is not None:
                        return resolved, lock_file

                else:

                    resolved, lock_file = self._resolve_remote(
                        rq=rq, dep=dep, local_sink_id=local_sink_id, local_resource_factory=self._qf._local, date=date,alternative_urls=remote_urls
                    )
                    if resolved is not None:
                        return resolved, lock_file

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
            alternative_urls: Optional[List[str]] = None,

    ) -> Tuple[Optional[ResolvedDependency], Optional[LockProduct]]:

        assert rq.product.filename.value is not None, "Remote resolution requires filename to be filled in"

        # local_path = self._download_result(rq, dest_dir)
        local_path: Optional[Path] = self._fetcher.download_one(
            query=rq,
            local_resource_id=local_sink_id,
            local_factory=local_resource_factory,
            date = date,
        )
        if local_path is None:
            return (None, None)
        lock_file: LockProduct = build_lock_product(
            sink=local_path,
            url=_build_remote_url(rq),
            name=dep.spec,
            description=dep.description or "",
            alternative_urls=alternative_urls,
        )
        write_lock_product(lock_file)
        resolved = self._make_resolved(
            dep,
            status="downloaded",
            lock_file=lock_file,
        )
        
        return (resolved, lock_file)

    def _resolve_local(
            self,
            rq: ResourceQuery,
            dep: Dependency,
            local_sink_id: str,
            local_resource_factory:LocalResourceFactory,
            date: datetime.datetime,
            alternative_urls: Optional[List[str]] = None,

    ) -> Tuple[Optional[ResolvedDependency], Optional[LockProduct]]:

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
        if (existing_lock := get_lock_product(source_path)) is None:
            existing_lock = build_lock_product(
                sink=source_path,
                url="",
                name=dep.spec,
                description=dep.description or "",
                alternative_urls=alternative_urls,
            )
            write_lock_product(existing_lock)

        resolved = self._make_resolved(
            dep,
            status="local",
            lock_file=existing_lock,
        )
        
        return (resolved, existing_lock)


    @staticmethod
    def _make_resolved(
        dep: Dependency,
       
        *,
        status: str,
        lock_file: LockProduct,
    ) -> ResolvedDependency:
        """Build a :class:`ResolvedDependency` from a ResourceQuery."""
  

        return ResolvedDependency(
            spec=dep.spec,
            required=dep.required,
            status=status,
            remote_url=lock_file.url,
            local_path=Path(lock_file.sink)
        )
