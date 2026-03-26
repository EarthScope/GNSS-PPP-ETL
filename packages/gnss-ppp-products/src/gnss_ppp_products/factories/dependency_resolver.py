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

import datetime
import hashlib
import json
import logging
from math import sin
import re
from pathlib import Path
from threading import local
from token import OP
from typing import Dict, List, Optional

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

        for dep in self.dep_spec.dependencies:
            resolved = self._resolve_one(dep, date, local_sink_id=local_sink_id)
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
        expanded_queries: List[ResourceQuery] = []
        for fq in fetched_queries:
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
                expanded_queries.append(rq)

        # Infer parameter values from the filename pattern if possible
        for rq in expanded_queries:
            updated_parameters: List[Parameter] = infer_from_regex(  # type: ignore
                regex=rq.product.filename.pattern,  # type: ignore
                filename=rq.product.filename.value,  # type: ignore
                parameters=rq.product.parameters,
            )  
            if updated_parameters:
                rq.product.parameters = updated_parameters
            classification_results = self._product_environment.classify(filename=rq.product.filename.value, parameters=rq.product.parameters)
            if classification_results:
                class_parameters:Dict[str,str] = classification_results.get("parameters", {}) # TODO make the classification results more structured so we don't have to do this stringly-typed dance
                for p in rq.product.parameters:
                    if p.name in class_parameters and p.value is None:
                        p.value = class_parameters[p.name]

        expanded_queries = self._sort_by_preferences(expanded_queries)

        '''
        1. Sort by preferences
        2. Group by matching parameter sets, sort so that local matches come first within each group
        
        '''
        parameter_groups: Dict[str, List[ResourceQuery]] = {}
        for rq in expanded_queries:
            key_list = [f"{p.name}={p.value}" for p in rq.product.parameters if p.value is not None]
            sorted_key_list = list(sorted(key_list, key=lambda x: x.split("=")[0]))  # Sort by parameter name for consistent grouping
            key_string = "|".join(sorted_key_list)
            parameter_groups.setdefault(key_string, []).append(rq)

        protocol_sort_order = ["FILE", "LOCAL", "FTP", "FTPS", "HTTP", "HTTPS"]
        for key, group in parameter_groups.items():
            group.sort(key=lambda rq: protocol_sort_order.index((rq.server.protocol or "").upper()) if (rq.server.protocol or "").upper() in protocol_sort_order else len(protocol_sort_order))

        # If our first query has been found locally, we can pick that.

        # # Partition into local and remote
        # local_queries = [
        #     q for q in expanded_queries
        #     if (q.server.protocol or "").upper() in ("FILE", "LOCAL", "")
        # ]
        # remote_queries = [
        #     q for q in expanded_queries
        #     if (q.server.protocol or "").upper() not in ("FILE", "LOCAL", "")
        # ]

        # # Pair local and remote queries by their filename pattern.
        # pairs: List[tuple[ResourceQuery, Optional[ResourceQuery]]] = []
        # for lq in local_queries:
        #     local_filename = lq.product.filename.value
        #     for idx,rq in enumerate(remote_queries):
        #         remote_filename = rq.product.filename.value
        #         if local_filename == remote_filename:
        #             pairs.append((lq, remote_queries.pop(idx)))
        #             break

        # Phase 1: check local disk
        for parameter_group in parameter_groups.values():
            for rq in parameter_group:
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
                val = _get_param_value(rq, _pn).upper()
                try:
                    return _s.index(val)
                except ValueError:
                    return len(_s)

            queries = sorted(queries, key=_key)

        return queries

    def _resolve_remote(
            self,
            rq: ResourceQuery,
            dep: Dependency,
            local_sink_id: str,
            local_resource_factory:LocalResourceFactory,
            date: datetime.datetime,

    ) -> Optional[ResolvedDependency]:

        assert rq.product.filename.value is not None, "Remote resolution requires filename to be filled in"

        #local_path = self._download_result(rq, dest_dir)
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
        )
        self._write_file_lock(local_path, resolved)
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
        sink_directory = local_resource_factory.sink_product(rq.product, local_sink_id, date).directory.value
        assert sink_directory is not None, "Sink product must have a directory value"
        sink_directory = Path(sink_directory)
        if not sink_directory == source_directory:
            sink_directory.mkdir(parents=True, exist_ok=True)
            # Copy the file to the sink directory
            dest_path = sink_directory / filename
            if not dest_path.exists():
                dest_path.write_bytes(source_path.read_bytes())
                logger.info(f"Copied local file {source_path} to sink directory {dest_path}")
            source_path = dest_path

        file_hash = _hash_file(source_path)
        file_size = source_path.stat().st_size
        resolved = self._make_resolved(
            dep, rq,
            status="local",
            local_path=source_path,
            file_hash=file_hash,
            file_size=file_size,
        )
        return resolved

    def _try_remote(
        self,
        dep: Dependency,
        rq: ResourceQuery,
        *,
        rank: int,
        download: bool,
    ) -> Optional[ResolvedDependency]:
        """Use ResourceFetcher to search (and optionally download) one query."""
        from gnss_ppp_products.factories.resource_fetcher import FetchResult

        results = self._fetcher.search([rq])
        if not results:
            return None

        fr: FetchResult = results[0]
        if not fr.found:
            return None

        label = _get_param_value(rq, "AAA") or rq.server.hostname
        local_path: Optional[Path] = None
        file_hash = ""
        file_size: int | None = None

        if download:
            local_path = self._download_result(rq, fr)
            if local_path is not None:
                file_hash = _hash_file(local_path)
                file_size = local_path.stat().st_size

        resolved = self._make_resolved(
            dep, rq,
            status="downloaded" if local_path else "remote",
            local_path=local_path,
            file_hash=file_hash,
            file_size=file_size,
        )

        if local_path is not None:
            self._write_file_lock(local_path, resolved)

        return resolved

    def _download_result(
        self,
        rq: ResourceQuery,
        dest_dir: Path,
    ) -> Optional[Path]:
        """Download the first matched file from a FetchResult."""

        assert dest_dir.exists() and dest_dir.is_dir(), "Destination directory must exist for download"
        directory = rq.directory.value
        assert directory is not None, "Directory must be specified for download"
        filename = rq.product.filename.value 
        assert filename is not None, "Filename must be specified for download"
        protocol = (rq.server.protocol or "").upper()
        hostname = rq.server.hostname

        if protocol in ("FTP", "FTPS"):
            return self._download_ftp(
                hostname, directory, filename, dest_dir,
                use_tls=(protocol == "FTPS"),
            )
        if protocol in ("HTTP", "HTTPS"):
            return self._download_http(
                hostname, directory, filename, dest_dir,
            )

        logger.warning("Unsupported protocol for download: %s", protocol)
        return None

    def _download_ftp(
        self,
        hostname: str,
        directory: str,
        filename: str,
        dest_dir: Path,
        *,
        use_tls: bool = False,
    ) -> Optional[Path]:
        from gnss_ppp_products.server.ftp import ftp_download_file

        dest = dest_dir / filename
        if ftp_download_file(hostname, directory, filename, dest, use_tls=use_tls):
            logger.info("Downloaded %s → %s", filename, dest)
            return dest
        return None

    def _download_http(
        self,
        hostname: str,
        directory: str,
        filename: str,
        dest_dir: Path,
    ) -> Optional[Path]:
        from gnss_ppp_products.server.http import http_get_file

        result = http_get_file(hostname, directory, filename, dest_dir)
        if result is not None:
            logger.info("Downloaded %s → %s", filename, result)
            return result
        return None

    @staticmethod
    def _get_file_lock(local_path: Path) -> Optional[LockProduct]:
        """Check for a ``<filename>.lock`` sidecar and return its path if it exists."""
        lock_path = local_path.parent / f"{local_path.name}.lock"
        if lock_path.exists() and lock_path.is_file():
            with open(lock_path,'r') as f:
                lock_data = json.load(f)
                lock_product = LockProduct.model_validate(lock_data)
            return lock_product
        return None

    @staticmethod
    def _write_file_lock(local_path: Path, resolved: ResolvedDependency) -> None:
        """Write a ``<filename>.lock`` JSON sidecar next to the downloaded file."""
        if resolved.lockfile is None:
            return
        lock_path = local_path.parent / f"{local_path.name}.lock"
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
    ) -> ResolvedDependency:
        """Build a :class:`ResolvedDependency` from a ResourceQuery."""
        from gnss_ppp_products.specifications.dependencies.lockfile import LockProduct

        remote_url = _build_remote_url(rq)
        regex = _file_pattern(rq)

        lock_product: Optional[LockProduct] = DependencyResolver._get_file_lock(local_path)
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
