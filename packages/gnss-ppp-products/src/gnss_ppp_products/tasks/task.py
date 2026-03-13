"""
Task — orchestrate product dependency resolution.

A :class:`Task` ties together three concerns:

1. **Product dependency definitions** — *what* products are needed.
2. **Remote source definitions** — ``GNSSCenterConfig`` objects that
   know how to generate file queries with server information.
3. **Local source definitions** — a ``LocalStorageConfig`` that maps
   product types to directories on disk.

Typical usage::

    from gnss_ppp_products.tasks import Task, ProductDependency, DependencyType

    task = Task(
        date=datetime.date(2025, 1, 15),
        dependencies=[
            ProductDependency(type=DependencyType.PRODUCTS),
            ProductDependency(type=DependencyType.RINEX),
            ProductDependency(type=DependencyType.ANTENNAE),
        ],
        centers=[igs_center, wuhan_center],
        local_storage_root="/data/gnss",
    )

    result = task.resolve()       # search local, build remote queries
    print(result.summary())       # "TaskResult: 42 queries — 38 found locally …"

    task.download(result)         # download missing products
    print(result.summary())       # "TaskResult: 42 queries — 38 found locally, 4 downloaded …"
"""

from __future__ import annotations

import datetime
import logging
from pathlib import Path
from typing import List, Optional, Union

from ..assets.center.config import GNSSCenterConfig
from ..local.config import LocalStorageConfig
from ..local.query import LocalFileQuery
from ..server.ftp import ftp_download_file, ftp_list_directory, ftp_find_best_match_in_listing
from ..server.http import http_get_file, http_list_directory, extract_filenames_from_html

from .dependencies import DependencyType, ProductDependency
from .results import FileQuery, ResolvedProduct, TaskResult

logger = logging.getLogger(__name__)


class Task:
    """Orchestrate product dependency resolution.

    Parameters
    ----------
    date : datetime.date
        The processing date for which products are needed.
    dependencies : list[ProductDependency]
        Declarations of what product categories are required.
    centers : list[GNSSCenterConfig]
        Remote source definitions — each center's YAML config loaded
        into a Pydantic model.  Used to generate concrete file queries
        with server information attached.
    local_storage : str, Path, or LocalStorageConfig
        Root directory for local product storage or an existing LocalStorageConfig instance.
    """

    def __init__(
        self,
        dependencies: List[ProductDependency],
        centers: List[GNSSCenterConfig],
        local_storage: Union[str, Path, LocalStorageConfig],
    ) -> None:
        
        self.dependencies = dependencies
        self.centers = centers
        if isinstance(local_storage, LocalStorageConfig):
            self.local_config = local_storage
        else:
            self.local_config = LocalStorageConfig(local_storage)
        self._local_query = LocalFileQuery(self.local_config)

    # ------------------------------------------------------------------
    # Query generation
    # ------------------------------------------------------------------

    def _build_queries(self, date: datetime.datetime | datetime.date) -> dict[DependencyType, list[FileQuery]]:
        """Generate file queries for each dependency from all centers.

        Iterates over every dependency type, calls the matching
        ``build_*_queries`` method on each center, and collects the
        resulting :class:`FileQuery` objects keyed by dependency type.
        """
        queries: dict[DependencyType, list[FileQuery]] = {}

        for dep in self.dependencies:
            dep_queries: list[FileQuery] = []
            for center in self.centers:
                match dep.type:
                    case DependencyType.PRODUCTS:
                        dep_queries.extend(center.build_product_queries(date))
                    case DependencyType.RINEX:
                        dep_queries.extend(center.build_rinex_queries(date))
                    case DependencyType.ANTENNAE:
                        dep_queries.extend(center.build_antennae_queries(date))
                    case DependencyType.TROPOSPHERE:
                        dep_queries.extend(center.build_troposphere_queries(date))
                    case DependencyType.OROGRAPHY:
                        dep_queries.extend(center.build_orography_queries())
                    case DependencyType.LEO:
                        dep_queries.extend(center.build_leo_queries(date))
                    case DependencyType.REFERENCE_TABLES:
                        dep_queries.extend(center.build_reference_table_queries())
            queries[dep.type] = dep_queries

        return queries

    def resolve(self, date: datetime.datetime | datetime.date) -> TaskResult:
        """Resolve all dependencies for the given date.

        First builds file queries for each dependency type, then searches
        local storage for matching files.  Returns a summary of what was
        found locally and what is still missing (and can be passed to
        :meth:`download`).
        """
        queries = self._build_queries(date)
        task_result = self._resolve_local(queries)
        task_result = self._resolve_remote(task_result)
        return task_result

    # ------------------------------------------------------------------
    # Local resolution
    # ------------------------------------------------------------------

    def _resolve_local(self, all_queries: dict[DependencyType, list[FileQuery]]) -> TaskResult:
        """Search local storage for every file query.

        Returns a :class:`TaskResult` where each query is marked as
        found (with local paths) or missing.  Missing queries retain
        their ``server`` attribute so they can be passed to
        :meth:`download` to fetch from remote.
        """
        resolved: list[ResolvedProduct] = []

        for dep_type, queries in all_queries.items():
            for query in queries:
                local_matches = self._local_query.search(query)
                resolved.append(
                    ResolvedProduct(
                        dependency_type=dep_type,
                        query=query,
                        local_paths=local_matches,
                    )
                )

        result = TaskResult(resolved=resolved)
        logger.info(result.summary())
        return result

    # ------------------------------------------------------------------
    # Remote download
    # ------------------------------------------------------------------

    def _resolve_remote(self, result: TaskResult) -> TaskResult:
        """Download products not found locally.

        For each missing product in *result*, queries the remote server
        for matching files and downloads the first match into the
        appropriate local directory.

        Parameters
        ----------
        result : TaskResult, optional
            A previous :meth:`_resolve_local` result.  If ``None``, calls
            :meth:`_resolve_local` first.

        Returns
        -------
        TaskResult
            The same (mutated) result with ``downloaded_path`` populated
            on successfully downloaded products.
        """
        for rp in result.missing:
            query = rp.query
            if query.server is None:
                logger.warning("Skipping query with no server: %s", query.filename)
                continue

            dest_dir = self._local_query.resolve_directory(query)
            downloaded = self._download_query(query, dest_dir)
            if downloaded is not None:
                rp.downloaded_path = downloaded

        logger.info(result.summary())
        return result

    def _download_query(self, query: FileQuery, dest_dir: Path) -> Optional[Path]:
        """Attempt to download a single query from its server.

        Searches the remote directory listing for a file matching the
        query's filename pattern, then downloads the first match.
        """
        server = query.server
        if server is None or query.filename is None or query.directory is None:
            return None

        protocol = server.protocol.value.upper()

        if protocol in ("FTP", "FTPS"):
            return self._download_ftp(server.hostname, query.directory, query.filename, dest_dir, use_tls=(protocol == "FTPS"))
        if protocol in ("HTTP", "HTTPS"):
            return self._download_http(server.hostname, query.directory, query.filename, dest_dir)

        logger.warning("Unsupported protocol %s for server %s", protocol, server.name)
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
        """Download from an FTP/FTPS server."""
        listing = ftp_list_directory(hostname, directory, use_tls=use_tls)
        if not listing:
            logger.debug("Empty FTP listing: %s/%s", hostname, directory)
            return None

        for match in ftp_find_best_match_in_listing(listing, filename):
            dest = dest_dir / match
            if ftp_download_file(
                hostname, directory, match, dest, use_tls=use_tls
            ):
                logger.info("Downloaded %s → %s", match, dest)
                return dest
            logger.warning("FTP download failed: %s/%s/%s", hostname, directory, match)

        return None

    def _download_http(
        self,
        hostname: str,
        directory: str,
        filename: str,
        dest_dir: Path,
    ) -> Optional[Path]:
        """Download from an HTTP/HTTPS server."""
        import re

        html = http_list_directory(hostname, directory)
        if html is None:
            logger.debug("No HTTP listing: %s/%s", hostname, directory)
            return None

        filenames = extract_filenames_from_html(html)
        for fname in filenames:
            if re.match(filename, fname):
                result = http_get_file(hostname, directory, fname, dest_dir)
                if result is not None:
                    logger.info("Downloaded %s → %s", fname, result)
                    return result

        return None
