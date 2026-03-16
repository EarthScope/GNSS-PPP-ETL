"""
Dependency resolver — local check + remote download.

Walks the preference cascade defined in a :class:`DependencySpec` to
resolve every declared dependency.  For each product the resolver:

1. Narrows the unified catalog (``ProductQuery``) to the product spec
   and any extra axis constraints.
2. Iterates through the preference cascade, narrowing by center (and
   solution / campaign when the product supports those axes).
3. Scans local storage for a matching file.
4. Optionally downloads from the remote server if nothing was found
   locally (``download=True``).

The first hit wins — once a product is found, the resolver moves on
to the next dependency.

Usage::

    from gnss_ppp_products.assets.dependency_spec import (
        DependencySpec, DependencyResolver,
    )

    spec = DependencySpec.from_yaml("pride_ppp_kin.yml")
    resolver = DependencyResolver(spec, base_dir="/data/gnss")

    result = resolver.resolve(datetime.date(2025, 1, 15))
    print(result.summary())
    print(result.table())

    # With downloads enabled:
    result = resolver.resolve(datetime.date(2025, 1, 15), download=True)
"""

from __future__ import annotations

import datetime
import logging
import re
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

from gnss_ppp_products.assets.query_spec.engine import ProductQuery, QueryResult
from gnss_ppp_products.server.ftp import (
    ftp_download_file,
    ftp_find_best_match_in_listing,
    ftp_list_directory,
)
from gnss_ppp_products.server.http import (
    extract_filenames_from_html,
    http_get_file,
    http_list_directory,
)

from .models import (
    Dependency,
    DependencyResolution,
    DependencySpec,
    ResolvedDependency,
    SearchPreference,
)

logger = logging.getLogger(__name__)


# ===================================================================
# Resolver
# ===================================================================


class DependencyResolver:
    """Resolve a :class:`DependencySpec` against local and remote resources.

    Parameters
    ----------
    dep_spec : DependencySpec
        The specification declaring required products and preferences.
    base_dir : Path or str
        Root of the local product tree.  Local directory for each
        product is resolved relative to this path.
    """

    def __init__(
        self,
        dep_spec: DependencySpec,
        base_dir: Path | str,
    ) -> None:
        self.dep_spec = dep_spec
        self.base_dir = Path(base_dir)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve(
        self,
        date: datetime.date,
        *,
        download: bool = False,
    ) -> DependencyResolution:
        """Resolve all dependencies for *date*.

        For each dependency, walks the preference cascade checking
        local storage first.  When ``download=True``, missing products
        are fetched from the remote server before giving up.

        Returns a :class:`DependencyResolution` with the outcome for
        every dependency.
        """
        q = ProductQuery(date=date)
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

    # ------------------------------------------------------------------
    # Single-dependency resolution
    # ------------------------------------------------------------------

    def _resolve_one(
        self,
        q: ProductQuery,
        dep: Dependency,
        *,
        download: bool,
    ) -> ResolvedDependency:
        """Resolve one dependency through the preference cascade."""

        # Narrow to the product spec (+ any per-dep constraints)
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

        # Pre-check which axes this product actually uses so we can
        # silently skip preference fields that don't apply.
        has_solutions = bool(q_spec.solutions())
        has_campaigns = bool(q_spec.campaigns())

        # No preferences → try all results without ordering
        if not self.dep_spec.preferences:
            return self._try_results(
                dep, q_spec.results,
                rank=-1, label="(default)",
                download=download,
            )

        # Walk the preference cascade
        for rank, pref in enumerate(self.dep_spec.preferences):
            q_pref = q_spec

            # Center is always applied
            try:
                q_pref = q_pref.narrow(center=pref.center)
            except ValueError:
                continue  # center not available for this product

            # Solution — only apply when the product has a solution axis
            if pref.solution and has_solutions:
                try:
                    q_pref = q_pref.narrow(solution=pref.solution)
                except ValueError:
                    continue  # solution not offered by this center

            # Campaign — only apply when the product has a campaign axis
            if pref.campaign and has_campaigns:
                try:
                    q_pref = q_pref.narrow(campaign=pref.campaign)
                except ValueError:
                    continue  # campaign not offered

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

        # Nothing worked
        return ResolvedDependency(
            spec=dep.spec, required=dep.required, status="missing",
        )

    # ------------------------------------------------------------------
    # Local + remote attempts
    # ------------------------------------------------------------------

    def _try_results(
        self,
        dep: Dependency,
        results: List[QueryResult],
        *,
        rank: int,
        label: str,
        download: bool,
    ) -> ResolvedDependency:
        """Try local storage, then optionally remote download."""

        # 1. Check local
        for r in results:
            local = self._check_local(r)
            if local is not None:
                return ResolvedDependency(
                    spec=dep.spec, required=dep.required,
                    status="local",
                    query_result=r, local_path=local,
                    preference_rank=rank, preference_label=label,
                )

        # 2. Try remote download
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

    # ------------------------------------------------------------------
    # Local file check
    # ------------------------------------------------------------------

    def _check_local(self, r: QueryResult) -> Optional[Path]:
        """Return the first matching local file, or ``None``."""
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

    # ------------------------------------------------------------------
    # Remote download
    # ------------------------------------------------------------------

    def _download(self, r: QueryResult) -> Optional[Path]:
        """Download a product from its remote server to local storage."""
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
        """List remote FTP directory, match regex, download first hit."""
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
        """List remote HTTP directory, match regex, download first hit."""
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


# ===================================================================
# Helpers
# ===================================================================


def _strip_protocol(url: str) -> str:
    """Strip protocol prefix from a server URL → hostname only."""
    parsed = urlparse(url)
    return parsed.hostname or url
