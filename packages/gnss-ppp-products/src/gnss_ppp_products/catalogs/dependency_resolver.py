"""
Dependency resolver — local check + remote download.
"""

from __future__ import annotations

import datetime
import logging
import re
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

from gnss_ppp_products.catalogs.query_engine import ProductQuery, QueryResult
from gnss_ppp_products.specifications.dependencies import (
    Dependency,
    DependencyResolution,
    DependencySpec,
    ResolvedDependency,
)

logger = logging.getLogger(__name__)


class DependencyResolver:
    """Resolve a :class:`DependencySpec` against local and remote resources.

    Requires an ``environment`` instance that provides a ``.query(date)``
    method returning a :class:`ProductQuery`.
    """

    def __init__(
        self,
        dep_spec: DependencySpec,
        base_dir: Path | str,
        *,
        environment=None,
    ) -> None:
        self.dep_spec = dep_spec
        self.base_dir = Path(base_dir)
        self._env = environment

    def resolve(
        self,
        date: datetime.date,
        *,
        download: bool = False,
    ) -> DependencyResolution:
        if self._env is None:
            raise TypeError(
                "DependencyResolver requires an environment instance."
            )
        q = self._env.query(date)
        results: List[ResolvedDependency] = []

        for dep in self.dep_spec.dependencies:
            resolved = self._resolve_one(q, dep, download=download)
            results.append(resolved)

        resolution = DependencyResolution(
            spec_name=self.dep_spec.name,
            resolved=results,
        )
        logger.info(resolution.summary())
        return resolution

    def _resolve_one(
        self,
        q: ProductQuery,
        dep: Dependency,
        *,
        download: bool,
    ) -> ResolvedDependency:
        try:
            q_spec = q.narrow(spec=dep.spec, **dep.constraints)
        except ValueError:
            return ResolvedDependency(
                spec=dep.spec, required=dep.required, status="missing",
            )

        if not q_spec.results:
            return ResolvedDependency(
                spec=dep.spec, required=dep.required, status="missing",
            )

        if not self.dep_spec.preferences:
            return self._try_results(
                dep, q_spec.results,
                rank=-1, label="(default)",
                download=download,
            )

        for rank, pref in enumerate(self.dep_spec.preferences):
            q_pref = q_spec

            try:
                q_pref = q_pref.narrow(center=pref.center)
            except ValueError:
                continue

            if pref.solution and q_pref.solutions():
                try:
                    q_pref = q_pref.narrow(solution=pref.solution)
                except ValueError:
                    continue

            if pref.campaign and q_pref.campaigns():
                try:
                    q_pref = q_pref.narrow(campaign=pref.campaign)
                except ValueError:
                    continue

            if not q_pref.results:
                continue

            label = pref.center
            if pref.solution:
                label += f"/{pref.solution}"
            if pref.campaign:
                label += f"/{pref.campaign}"

            result = self._try_results(
                dep, q_pref.results,
                rank=rank, label=label,
                download=download,
            )
            if result.status != "missing":
                return result

        return ResolvedDependency(
            spec=dep.spec, required=dep.required, status="missing",
        )

    def _try_results(
        self,
        dep: Dependency,
        results: List[QueryResult],
        *,
        rank: int,
        label: str,
        download: bool,
    ) -> ResolvedDependency:
        for r in results:
            local = self._check_local(r)
            if local is not None:
                return ResolvedDependency(
                    spec=dep.spec, required=dep.required,
                    status="local",
                    query_result=r, local_path=local,
                    preference_rank=rank, preference_label=label,
                )

        if download:
            for r in results:
                downloaded = self._download(r)
                if downloaded is not None:
                    return ResolvedDependency(
                        spec=dep.spec, required=dep.required,
                        status="downloaded",
                        query_result=r, local_path=downloaded,
                        preference_rank=rank, preference_label=label,
                    )

        return ResolvedDependency(
            spec=dep.spec, required=dep.required, status="missing",
        )

    def _check_local(self, r: QueryResult) -> Optional[Path]:
        if not r.local_directory:
            return None
        d = self.base_dir / r.local_directory
        if not d.exists():
            return None
        if not r.regex:
            return None
        pat = re.compile(r.regex, re.IGNORECASE)
        for f in sorted(d.iterdir()):
            if f.is_file() and pat.search(f.name):
                return f
        return None

    def _download(self, r: QueryResult) -> Optional[Path]:
        if not r.remote_server or not r.remote_directory or not r.regex:
            return None
        if not r.local_directory:
            return None

        dest_dir = self.base_dir / r.local_directory
        dest_dir.mkdir(parents=True, exist_ok=True)

        hostname = _strip_protocol(r.remote_server)
        protocol = r.remote_protocol.upper()

        if protocol in ("FTP", "FTPS"):
            return self._download_ftp(
                hostname, r.remote_directory, r.regex, dest_dir,
                use_tls=(protocol == "FTPS"),
            )
        if protocol in ("HTTP", "HTTPS"):
            return self._download_http(
                hostname, r.remote_directory, r.regex, dest_dir,
            )

        logger.warning("Unsupported protocol: %s", protocol)
        return None

    def _download_ftp(
        self,
        hostname: str,
        directory: str,
        regex: str,
        dest_dir: Path,
        *,
        use_tls: bool = False,
    ) -> Optional[Path]:
        from gnss_ppp_products.server.ftp import (
            ftp_download_file,
            ftp_find_best_match_in_listing,
            ftp_list_directory,
        )
        listing = ftp_list_directory(hostname, directory, use_tls=use_tls)
        if not listing:
            return None
        for match in ftp_find_best_match_in_listing(listing, regex):
            dest = dest_dir / match
            if ftp_download_file(
                hostname, directory, match, dest, use_tls=use_tls,
            ):
                logger.info("Downloaded %s → %s", match, dest)
                return dest
        return None

    def _download_http(
        self,
        hostname: str,
        directory: str,
        regex: str,
        dest_dir: Path,
    ) -> Optional[Path]:
        from gnss_ppp_products.server.http import (
            extract_filenames_from_html,
            http_get_file,
            http_list_directory,
        )
        html = http_list_directory(hostname, directory)
        if html is None:
            return None
        pat = re.compile(regex, re.IGNORECASE)
        for fname in extract_filenames_from_html(html):
            if pat.search(fname):
                result = http_get_file(hostname, directory, fname, dest_dir)
                if result is not None:
                    logger.info("Downloaded %s → %s", fname, result)
                    return result
        return None


def _strip_protocol(url: str) -> str:
    parsed = urlparse(url)
    return parsed.hostname or url
