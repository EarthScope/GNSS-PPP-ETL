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
import logging
import re
from pathlib import Path
from typing import List, Optional

from gnss_ppp_products.specifications.remote.resource import ResourceQuery
from gnss_ppp_products.specifications.dependencies.dependencies import (
    Dependency,
    DependencyResolution,
    DependencySpec,
    ResolvedDependency,
    SearchPreference,
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
    return f"{protocol}://{hostname}{sep}{directory}{trail}{filename}"


def _file_pattern(rq: ResourceQuery) -> str:
    """Return the filename regex pattern from a ResourceQuery."""
    if rq.product.filename:
        return rq.product.filename.value or rq.product.filename.pattern
    return ""


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
        base_dir: Path | str,
        *,
        query_factory,
        fetcher=None,
    ) -> None:
        self.dep_spec = dep_spec
        self.base_dir = Path(base_dir)
        self._qf = query_factory
        self._fetcher = fetcher

    def resolve(
        self,
        date: datetime.datetime,
        *,
        download: bool = False,
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
            resolved = self._resolve_one(dep, date, download=download)
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
        *,
        download: bool,
    ) -> ResolvedDependency:
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
            return ResolvedDependency(
                spec=dep.spec, required=dep.required, status="missing",
            )

        # Partition into local and remote
        local_queries = [
            q for q in queries
            if (q.server.protocol or "").upper() in ("FILE", "LOCAL", "")
        ]
        remote_queries = [
            q for q in queries
            if (q.server.protocol or "").upper() not in ("FILE", "LOCAL", "")
        ]

        # Apply preference sorting
        remote_queries = self._sort_by_preferences(remote_queries)

        # Phase 1: check local disk
        for rq in local_queries:
            local_path = self._check_local(rq)
            if local_path is not None:
                return self._make_resolved(
                    dep, rq, status="local",
                    local_path=local_path,
                    rank=-1, label="local",
                )

        # Phase 2: search / download remote
        if self._fetcher is not None:
            for rank, rq in enumerate(remote_queries):
                result = self._try_remote(
                    dep, rq,
                    rank=rank, download=download,
                )
                if result is not None:
                    return result

        return ResolvedDependency(
            spec=dep.spec, required=dep.required, status="missing",
        )

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

    def _check_local(self, rq: ResourceQuery) -> Optional[Path]:
        """Check whether the local directory has a matching file."""
        directory = rq.directory.value or rq.directory.pattern
        d = Path(directory)
        if not d.is_absolute():
            d = self.base_dir / d
        if not d.exists():
            return None
        pattern = _file_pattern(rq)
        if not pattern:
            return None
        pat = re.compile(pattern, re.IGNORECASE)
        for f in sorted(d.iterdir()):
            if f.is_file() and pat.search(f.name):
                return f
        return None

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

        if download:
            local_path = self._download_result(rq, fr)

        return self._make_resolved(
            dep, rq,
            status="downloaded" if local_path else "remote",
            local_path=local_path,
            rank=rank,
            label=label,
        )

    def _download_result(
        self,
        rq: ResourceQuery,
        fr,
    ) -> Optional[Path]:
        """Download the first matched file from a FetchResult."""
        if not fr.matched_filenames:
            return None

        directory = rq.directory.value or rq.directory.pattern
        dest_dir = self.base_dir / directory.lstrip("/")
        dest_dir.mkdir(parents=True, exist_ok=True)

        filename = fr.matched_filenames[0]
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
    def _make_resolved(
        dep: Dependency,
        rq: ResourceQuery,
        *,
        status: str,
        local_path: Optional[Path],
        rank: int,
        label: str,
    ) -> ResolvedDependency:
        """Build a :class:`ResolvedDependency` from a ResourceQuery."""
        return ResolvedDependency(
            spec=dep.spec,
            required=dep.required,
            status=status,
            query_result=rq,
            local_path=local_path,
            preference_rank=rank,
            preference_label=label,
            remote_url=_build_remote_url(rq),
            regex=_file_pattern(rq),
            format=_get_param_value(rq, "FMT"),
            version=_get_param_value(rq, "TTT"),
            variant=_get_param_value(rq, "PPP"),
            description=dep.description,
        )
