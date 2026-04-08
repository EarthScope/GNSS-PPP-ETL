"""Author: Franklyn Dunbar

Dependency resolver — resolve a DependencySpec via SearchPlanner.

Two-phase resolution:
  1. **Local** — check ``base_dir`` for files already on disk.
  2. **Remote** — use :class:`WormHole` to search/download.

Preferences are applied by sorting ``SearchTarget`` results according
to the ``SearchPreference.parameter`` / ``sorting`` cascade defined in
the dependency spec.
"""

from __future__ import annotations

from collections import defaultdict
import datetime
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
from functools import partial

from gnss_product_management.environments import ProductRegistry
from gnss_product_management.specifications.remote.resource import SearchTarget
from gnss_product_management.specifications.dependencies.dependencies import (
    Dependency,
    DependencyResolution,
    DependencySpec,
    ResolvedDependency,
)
from gnss_product_management.factories.search_planner import SearchPlanner
from gnss_product_management.factories.remote_transport import WormHole
from gnss_product_management.specifications.products.product import (
    infer_from_regex,
)
from gnss_product_management.specifications.parameters.parameter import Parameter
from gnss_product_management.factories.local_search_planner import LocalSearchPlanner
from gnss_product_management.lockfile import (
    LockProduct,
    LockfileManager,
    build_lock_product,
    get_lock_product,
    write_lock_product,
    get_package_version,
)
from gnss_product_management.utilities.helpers import decompress_gzip
from gnss_product_management.utilities.paths import AnyPath, as_path

logger = logging.getLogger(__name__)


def _get_param_value(rq: SearchTarget, param_name: str) -> str:
    """Extract a parameter value from a SearchTarget's product.

    Args:
        rq: The target to inspect.
        param_name: Parameter name to extract.

    Returns:
        The parameter value, or ``""`` if not found.
    """
    for p in rq.product.parameters:
        if p.name == param_name and p.value is not None:
            return p.value
    return ""


def _build_remote_url(rq: SearchTarget) -> str:
    """Construct a full remote URL from a SearchTarget.

    Args:
        rq: The target to build a URL for.

    Returns:
        Fully qualified URL string.
    """
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


class DependencyResolver:
    """Resolve a :class:`DependencySpec` using :class:`SearchPlanner`.

    Attributes:
        dep_spec: The dependency specification to resolve.

    Args:
        dep_spec: The dependency specification to resolve.
        query_factory: A :class:`SearchPlanner` wired to the desired centres.
        product_environment: The product registry for classification.
        fetcher: A :class:`WormHole` for remote search/download.
    """

    def __init__(
        self,
        dep_spec: DependencySpec,
        query_factory: SearchPlanner,
        product_environment: ProductRegistry,
        fetcher: WormHole,
    ) -> None:
        """Initialise the resolver.

        Args:
            dep_spec: The dependency specification to resolve.
            query_factory: Search planner wired to the desired centres.
            product_environment: Registry for product classification.
            fetcher: Transport for remote search/download.
        """
        self.dep_spec = dep_spec
        self._qf: SearchPlanner = query_factory
        self._fetcher = fetcher
        self._product_environment = product_environment

    def resolve(
        self,
        date: datetime.datetime,
        local_sink_id: str,
    ) -> Tuple[DependencyResolution, Optional[AnyPath]]:
        """Resolve every dependency in the spec for *date*.

        Fast path: if a lockfile already exists for
        ``(package, task, date, version)`` skip resolution entirely.

        Otherwise resolves remaining dependencies in parallel using a
        :class:`ThreadPoolExecutor`, then auto-generates an aggregate
        lockfile from the per-file sidecars.

        Args:
            date: Target date (timezone-aware datetime).
            local_sink_id: Local resource identifier for storing results.

        Returns:
            A tuple of (:class:`DependencyResolution`, lockfile path).
        """
        version = get_package_version()
        lockfile_dir = self._qf._local.lockfile_dir(local_sink_id)
        manager = LockfileManager(lockfile_dir)

        # --- Fast path: skip if lockfile exists ----------------------
        existing = manager.load(
            package=self.dep_spec.package,
            task=self.dep_spec.task,
            date=date,
            version=version,
        )
        if existing is not None:
            lf_path = manager.lockfile_path(
                package=self.dep_spec.package,
                task=self.dep_spec.task,
                date=date,
                version=version,
            )
            logger.info(
                "Lockfile already exists for %s on %s — skipping resolution: %s",
                self.dep_spec.name,
                date.date(),
                lf_path,
            )
            results = []
            for lp in existing.products:
                dep = next(
                    (d for d in self.dep_spec.dependencies if d.spec == lp.name),
                    None,
                )
                results.append(
                    ResolvedDependency(
                        spec=lp.name,
                        required=dep.required if dep else True,
                        status="local",
                        remote_url=lp.url,
                        local_path=lp.sink,
                    )
                )
            resolution = DependencyResolution(
                spec_name=self.dep_spec.name, resolved=results
            )
            logger.info(resolution.summary())
            return resolution, lf_path

        # --- Full resolution path ------------------------------------
        results: List[ResolvedDependency] = []
        lockfiles: List[LockProduct] = []
        to_resolve = list(self.dep_spec.dependencies)

        partial_resolve_one = partial(
            self._resolve_one,
            date=date,
            local_sink_id=local_sink_id,
        )
        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = [executor.submit(partial_resolve_one, dep) for dep in to_resolve]
            for future in futures:
                if not future:
                    continue
                resolved, lock_file = future.result()
                if resolved:
                    results.append(resolved)
                if lock_file:
                    lockfiles.append(lock_file)

        # Auto-generate aggregate from collected sidecars
        if lockfiles:
            aggregate = manager.build_aggregate(
                products=lockfiles,
                package=self.dep_spec.package,
                task=self.dep_spec.task,
                date=date,
                version=version,
            )
            lf_path = manager.save(aggregate)
        else:
            lf_path = manager.lockfile_path(
                package=self.dep_spec.package,
                task=self.dep_spec.task,
                date=date,
                version=version,
            )

        resolution = DependencyResolution(
            spec_name=self.dep_spec.name,
            resolved=results,
        )
        logger.info(resolution.summary())
        return resolution, lf_path

    # ---- internal helpers ------------------------------------------

    def _resolve_one(
        self,
        dep: Dependency,
        date: datetime.datetime,
        local_sink_id: str,
    ) -> Tuple[Optional[ResolvedDependency], Optional[LockProduct]]:
        """Resolve a single dependency.

        Args:
            dep: The dependency to resolve.
            date: Target date.
            local_sink_id: Local resource identifier.

        Returns:
            A tuple of (resolved dependency, lock product) or
            (resolved-as-missing, ``None``).
        """
        try:
            queries = self._qf.get(
                date,
                product={"name": dep.spec},
                parameters=dep.constraints or None,
            )

        except (ValueError, KeyError) as exc:
            logger.debug("No queries for %s: %s", dep.spec, exc)
            return ResolvedDependency(
                spec=dep.spec,
                required=dep.required,
                status="missing",
            ), None

        if not queries:
            logger.warning(
                f"No queries returned for dependency {dep.spec} with constraints {dep.constraints}"
            )
            return ResolvedDependency(
                spec=dep.spec,
                required=dep.required,
                status="missing",
            ), None

        queries = self._sort_by_preferences(queries)

        # Search using the transport — returns List[SearchTarget] with filename.value set.
        logger.info(
            f"Searching for {len(queries)} queries for dependency {dep.spec}..."
        )
        expanded_queries: List[SearchTarget] = self._fetcher.search(queries)
        if not expanded_queries:
            logger.warning(f"No search results for dependency {dep.spec}")
            return ResolvedDependency(
                spec=dep.spec,
                required=dep.required,
                status="missing",
            ), None
        logger.info(f"Found {len(expanded_queries)} results for dependency {dep.spec}")

        # Update parameters from matched filenames.
        expanded_queries = [self._update_parameters(rq) for rq in expanded_queries]

        expanded_queries = self._sort_by_preferences(expanded_queries)
        filename_groups = defaultdict(list)
        for rq in expanded_queries:
            if rq.product.filename and rq.product.filename.value:
                filename_groups[rq.product.filename.value].append(rq)

        # sort by server protocol
        for key, group in filename_groups.items():
            filename_groups[key] = self._sort_by_protocol(group)

        for rq_index in expanded_queries:
            if not (rq_index.product.filename and rq_index.product.filename.value):
                continue
            remote_urls = [
                _build_remote_url(rq)
                for rq in filename_groups[rq_index.product.filename.value]
                if (rq.server.protocol or "").upper() not in ("FILE", "LOCAL", "")
            ]
            for rq in filename_groups[rq_index.product.filename.value]:
                if (rq.server.protocol or "").upper() in ("FILE", "LOCAL", ""):
                    resolved, lock_file = self._resolve_local(
                        rq=rq,
                        dep=dep,
                        local_sink_id=local_sink_id,
                        local_resource_factory=self._qf._local,
                        date=date,
                        alternative_urls=remote_urls,
                    )
                    if resolved is not None:
                        return resolved, lock_file

                else:
                    resolved, lock_file = self._resolve_remote(
                        rq=rq,
                        dep=dep,
                        local_sink_id=local_sink_id,
                        local_resource_factory=self._qf._local,
                        date=date,
                        alternative_urls=remote_urls,
                    )
                    if resolved is not None:
                        return resolved, lock_file

    def _sort_by_preferences(
        self,
        queries: List[SearchTarget],
    ) -> List[SearchTarget]:
        """Sort queries according to the preference cascade.

        Args:
            queries: SearchTarget objects to sort.

        Returns:
            Sorted list of targets.
        """
        if not self.dep_spec.preferences:
            return queries

        for pref in reversed(self.dep_spec.preferences):
            param_name = pref.parameter
            sorting = [v.upper() for v in pref.sorting]

            def _key(rq: SearchTarget, _pn=param_name, _s=sorting) -> int:
                try:
                    val = _get_param_value(rq, _pn).upper()
                    return _s.index(val)
                except (ValueError, TypeError):
                    return len(_s)

            queries = sorted(queries, key=_key)

        return queries

    def _sort_by_protocol(self, queries: List[SearchTarget]) -> List[SearchTarget]:
        """Sort queries by server protocol, preferring local/file over remote.

        Args:
            queries: SearchTarget objects to sort.

        Returns:
            Sorted list of targets.
        """
        protocol_sort_order = ["FILE", "LOCAL", "FTP", "FTPS", "HTTP", "HTTPS"]
        return sorted(
            queries,
            key=lambda rq: (
                protocol_sort_order.index((rq.server.protocol or "").upper())
                if (rq.server.protocol or "").upper() in protocol_sort_order
                else len(protocol_sort_order)
            ),
        )

    def _update_parameters(self, search_target: SearchTarget) -> SearchTarget:
        """Update a SearchTarget's parameters by re-interpolating patterns.

        Uses :func:`infer_from_regex` and :meth:`ProductRegistry.classify`
        to fill in parameter values from the matched filename.

        Args:
            search_target: The target to update.

        Returns:
            A deep copy of the target with updated parameters.
        """
        updated = search_target.model_copy(deep=True)
        if updated.product.filename is None:
            return updated
        updated_params: List[Parameter] = infer_from_regex(
            regex=updated.product.filename.pattern,  # type: ignore
            filename=updated.product.filename.value,  # type: ignore
            parameters=updated.product.parameters,
        )
        updated.product.parameters = updated_params
        classification_results = self._product_environment.classify(
            filename=updated.product.filename.value,
            parameters=updated.product.parameters,
        )
        if classification_results:
            class_parameters: Dict[str, str] = classification_results.get(
                "parameters", {}
            )  # TODO make the classification results more structured so we don't have to do this stringly-typed dance
            if updated.product.parameters is not None:
                for p in updated.product.parameters:
                    if p.name in class_parameters and p.value is None:
                        p.value = class_parameters[p.name]

        return updated

    def _resolve_remote(
        self,
        rq: SearchTarget,
        dep: Dependency,
        local_sink_id: str,
        local_resource_factory: LocalSearchPlanner,
        date: datetime.datetime,
        alternative_urls: Optional[List[str]] = None,
    ) -> Tuple[Optional[ResolvedDependency], Optional[LockProduct]]:
        """Download and resolve a remote dependency.

        Args:
            rq: The resolved target with filename value.
            dep: The dependency being resolved.
            local_sink_id: Target local resource identifier.
            local_resource_factory: Planner for local sink paths.
            date: Target date.
            alternative_urls: Alternative download URLs for the lockfile.

        Returns:
            A tuple of (resolved dependency, lock product) on success,
            or ``(None, None)`` on failure.
        """

        assert rq.product.filename.value is not None, (
            "Remote resolution requires filename to be filled in"
        )

        local_path: Optional[Path] = self._fetcher.download_one(
            query=rq,
            local_resource_id=local_sink_id,
            local_factory=local_resource_factory,
            date=date,
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
        rq: SearchTarget,
        dep: Dependency,
        local_sink_id: str,
        local_resource_factory: LocalSearchPlanner,
        date: datetime.datetime,
        alternative_urls: Optional[List[str]] = None,
    ) -> Tuple[Optional[ResolvedDependency], Optional[LockProduct]]:
        """Resolve a local dependency, optionally copying to the sink.

        Args:
            rq: The resolved target with filename value.
            dep: The dependency being resolved.
            local_sink_id: Target local resource identifier.
            local_resource_factory: Planner for local sink paths.
            date: Target date.
            alternative_urls: Alternative download URLs for the lockfile.

        Returns:
            A tuple of (resolved dependency, lock product).
        """

        source_directory = as_path(rq.server.hostname) / rq.directory.value
        assert source_directory.exists() and source_directory.is_dir(), (
            f"Local directory {source_directory} does not exist for query {rq}"
        )
        filename = rq.product.filename.value
        assert filename is not None, (
            f"Local resolution requires filename to be filled in for query {rq}"
        )

        source_path = source_directory / filename

        # Prefer an already-decompressed version on disk
        if source_path.suffix == ".gz":
            decompressed_path = as_path(str(source_path)[: -len(".gz")])
            if decompressed_path.exists() and decompressed_path.stat().st_size > 0:
                source_path = decompressed_path
                filename = source_path.name

        # If the file is not present in the local_sink resource, we can copy it there.
        sink_query = local_resource_factory.sink_product(
            rq.product, local_sink_id, date
        )
        sink_directory = (
            as_path(sink_query.server.hostname) / sink_query.directory.value
        )
        assert sink_directory is not None, "Sink product must have a directory value"
        if not sink_directory == source_directory:
            sink_directory.mkdir(parents=True, exist_ok=True)
            # Copy the file to the sink directory (works for local→local and cloud→cloud)
            dest_path = sink_directory / filename
            if not dest_path.exists():
                dest_path.write_bytes(source_path.read_bytes())
                logger.info(
                    f"Copied local file {source_path} to sink directory {dest_path}"
                )
            source_path = dest_path

        # Decompress gzip files in the sink (local only — cloud paths are not decompressed)
        if (
            isinstance(source_path, Path)
            and source_path.suffix == ".gz"
            and source_path.exists()
        ):
            decompressed = decompress_gzip(source_path)
            if decompressed is not None:
                source_path = decompressed

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
        """Build a :class:`ResolvedDependency` from a lock product.

        Args:
            dep: The dependency definition.
            status: Resolution status (``'local'``, ``'downloaded'``, etc.).
            lock_file: The lock product with path and URL info.

        Returns:
            A :class:`ResolvedDependency` instance.
        """

        return ResolvedDependency(
            spec=dep.spec,
            required=dep.required,
            status=status,
            remote_url=lock_file.url,
            local_path=lock_file.sink,
        )
