"""ResourceFetcher — protocol-agnostic file search and download."""

import datetime
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from gnss_ppp_products.specifications.products.product import ProductPath
from gnss_ppp_products.specifications.remote.resource import ResourceQuery
from gnss_ppp_products.factories.local_factory import LocalResourceFactory
from gnss_ppp_products.factories.connection_pool import ConnectionPoolFactory

logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    """Outcome of searching one ResourceQuery against its server."""

    query: ResourceQuery
    matched_filenames: List[str] = field(default_factory=list)
    error: Optional[str] = None
    download_dest: Optional[Path] = None

    @property
    def found(self) -> bool:
        return len(self.matched_filenames) > 0

    @property
    def downloaded(self) -> bool:
        return self.download_dest is not None and self.download_dest.exists()


class ResourceFetcher:
    """Search for files described by ResourceQuery objects.

    For each query, lists the remote (FTP/HTTP) or local directory, matches
    ``product.filename.pattern`` against the listing, and populates
    ``directory.value`` and ``filename.value`` on the query.

    Usage::

        queries = qf.get(date=..., product=..., parameters=...)
        fetcher = ResourceFetcher()
        results = fetcher.search(queries)

        for r in results:
            if r.found:
                print(r.query.server.hostname, r.matched_filenames)
    """

    def __init__(
        self,
        *,
        max_connections: int = 4,
    ) -> None:
        self._connection_pool_factory = ConnectionPoolFactory(max_connections=max_connections)

    def search(self, queries: List[ResourceQuery]) -> List[FetchResult]:
        """Search every query's server/directory for matching files."""
        # Get all unique hostenames.
        hostnames = set(q.server.hostname for q in queries)
        for hostname in hostnames:
            self._connection_pool_factory.add_connection(hostname)
        with ThreadPoolExecutor(max_workers=25) as pool:
            return list(pool.map(self._search_one, queries))

    def _search_one(self, query: ResourceQuery) -> FetchResult:
        """Search a single query's directory for matching files."""
        directory = self._get_directory(query)
        file_pattern = self._get_file_pattern(query)

        if not directory or not file_pattern:
            return FetchResult(
                query=query,
                error=f"Missing directory or file pattern: dir={directory!r}, pat={file_pattern!r}",
            )

        try:
            listing = self._connection_pool_factory.list_directory(query.server.hostname, directory)
        except Exception as e:
            return FetchResult(query=query, error=f"Listing failed: {e}")
        query.directory.value = directory  # type: ignore[union-attr]

        matches = self._match_files(listing, file_pattern)
        if matches:
            return FetchResult(query=query, matched_filenames=matches)
        return FetchResult(query=query, error="No matches found")

    # -- Pattern matching ------------------------------------------

    @staticmethod
    def _match_files(listing: List[str], file_pattern: str) -> List[str]:
        """Match filenames in a directory listing against a regex pattern."""
        # remove .lock files from listing before matching, since they are not actual resources
        listing = [f for f in listing if not f.endswith(".lock")]
        try:
            rx = re.compile(file_pattern, re.IGNORECASE)
            return [f for f in listing if rx.search(f)]
        except re.error:
            return [f for f in listing if file_pattern in f]

    # -- Value resolution ------------------------------------------

    @staticmethod
    def _resolve_values(query: ResourceQuery, directory: str, matched_filename: str) -> None:
        """Populate .value on the query's directory and filename ProductPaths."""
        if isinstance(query.directory, ProductPath):
            query.directory.value = directory
        if query.product.filename is not None and isinstance(query.product.filename, ProductPath):
            query.product.filename.value = matched_filename

    # -- Helpers ---------------------------------------------------

    @staticmethod
    def _get_directory(query: ResourceQuery) -> Optional[str]:
        """Extract the resolved directory string from a query."""
        d = query.directory
        if isinstance(d, ProductPath):
            return d.value or d.pattern
        if isinstance(d, str):
            return d
        return None

    @staticmethod
    def _get_file_pattern(query: ResourceQuery) -> Optional[str]:
        """Extract the file regex pattern from a query."""
        if query.product.filename is None:
            return None
        fn = query.product.filename
        if isinstance(fn, ProductPath):
            return fn.pattern
        if isinstance(fn, str):
            return fn
        return None


    def download_one(
        self,
        query: ResourceQuery,
        local_resource_id: str,
        local_factory: LocalResourceFactory,
        date: datetime.datetime,
    ) -> Optional[Path]:
        """Synchronously download all matched files for one FetchResult."""

        # TODO use fsspec ls to get file size in bytes, and skip download if size is zero.
        hostname = query.server.hostname

        destination_resource = local_factory.sink_product(query.product, local_resource_id, date)
        destination_dir = Path(destination_resource.server.hostname) / destination_resource.directory.value  # type: ignore[union-attr]
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination_path = destination_dir / query.product.filename.value  # type: ignore[union-attr]

        # Skip download if the file already exists and is non-empty
        if destination_path.exists() and destination_path.stat().st_size > 0:
            logger.info(f"Skipping download, file already exists: {destination_path}")
            return destination_path

        
        try:
            return self._connection_pool_factory.download_file(
                hostname=hostname,
                remote_path=str(Path(query.directory.value) / query.product.filename.value),  # type: ignore[union-attr]
                target_dir=destination_dir,
            )
        except Exception as e:
            logger.error(f"Download failed for {hostname}/{query.directory.value}/{query.product.filename.value}: {e}")
            return None
