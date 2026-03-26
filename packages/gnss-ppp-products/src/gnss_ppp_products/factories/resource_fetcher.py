"""ResourceFetcher — protocol-agnostic file search and download."""

import asyncio
import datetime
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Union

from gnss_ppp_products.server import protocol
from gnss_ppp_products.server.protocol import DirectoryAdapter
from gnss_ppp_products.server.ftp import FTPAdapter
from gnss_ppp_products.server.http import HTTPAdapter
from gnss_ppp_products.server.local import LocalAdapter
from gnss_ppp_products.specifications.products.product import ProductPath
from gnss_ppp_products.specifications.remote.resource import ResourceQuery
from gnss_ppp_products.factories.local_factory import LocalResourceFactory

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
        ftp_timeout: int = 60,
        download_timeout: int = 180,
    ) -> None:
        self._ftp_timeout = ftp_timeout
        self._download_timeout = download_timeout
        self._listing_cache: Dict[str, List[str]] = {}
        self._connectivity_cache: Dict[str, bool] = {}
        self._adapters: Dict[str, DirectoryAdapter] = {
            "FTP": FTPAdapter(timeout=ftp_timeout),
            "FTPS": FTPAdapter(timeout=ftp_timeout, use_tls=True),
            "HTTP": HTTPAdapter(timeout=download_timeout),
            "HTTPS": HTTPAdapter(timeout=download_timeout),
            "FILE": LocalAdapter(),
            "LOCAL": LocalAdapter(),
            "": LocalAdapter(),
        }

    def search(self, queries: List[ResourceQuery]) -> List[FetchResult]:
        """Search every query's server/directory for matching files."""
        return [self._search_one(q) for q in queries]

    def _search_one(self, query: ResourceQuery) -> FetchResult:
        """Search a single query's directory for matching files."""
        directory = self._get_directory(query)
        file_pattern = self._get_file_pattern(query)

        if not directory or not file_pattern:
            return FetchResult(
                query=query,
                error=f"Missing directory or file pattern: dir={directory!r}, pat={file_pattern!r}",
            )

        protocol = (query.server.protocol or "").upper()
        hostname = query.server.hostname

        cache_key = f"{protocol}://{hostname}/{directory}"

        if cache_key in self._listing_cache:
            listing = self._listing_cache[cache_key]
        else:
            adapter = self._adapters.get(protocol)
            if adapter is None:
                return FetchResult(query=query, error=f"Unsupported protocol: {protocol!r}")
            try:
                conn_key = f"{protocol}://{hostname}"
                if conn_key in self._connectivity_cache:
                    if not self._connectivity_cache[conn_key]:
                        raise ConnectionError(f"Server unreachable (cached): {hostname}")
                else:
                    reachable = adapter.can_connect(hostname)
                    self._connectivity_cache[conn_key] = reachable
                    if not reachable:
                        raise ConnectionError(f"Server unreachable: {hostname}")
                    
                logger.info(f"Listing {protocol} directory: {hostname}/{directory}")
                listing = adapter.list_directory(hostname, directory)
            except Exception as e:
                return FetchResult(query=query, error=f"Listing failed: {e}")
            # Cache non-local listings
            if protocol not in ("FILE", "LOCAL", ""):
                self._listing_cache[cache_key] = listing

        query.directory.value = directory  # type: ignore[union-attr]

        matches = self._match_files(listing, file_pattern)
        logger.info(f"Found {len(matches)} matches for {hostname}/{directory} with pattern {file_pattern!r}")
        if matches:
            return FetchResult(
                    query=query,
                    matched_filenames=matches
                )
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

    # -- Async download --------------------------------------------

    async def download(
        self,
        results: List[ResourceQuery],
        local_resource_id:str,
        local_factory: LocalResourceFactory,
        date: datetime.datetime,
        *,
        max_workers: int = 4,
    ) -> List[FetchResult]:
        """Download found remote files to the complementary local directory.

        For each ``FetchResult`` with ``found=True`` and a non-local protocol,
        resolves the local directory via *local_factory*, creates it, and
        downloads every matched file into it.

        Downloads run concurrently in a thread pool (FTP/HTTP are blocking IO).
        """
        loop = asyncio.get_running_loop()
        remote_found = [
            fr for fr in results
            if fr.found and (fr.query.server.protocol or "").upper() not in ("FILE", "LOCAL", "")
        ]
        if not remote_found:
            return results

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            tasks = [
                loop.run_in_executor(pool, self.download_one, fr, local_factory, date)
                for fr in remote_found
            ]
            await asyncio.gather(*tasks)

        return results

    def download_one(
        self,
        query: ResourceQuery,
        local_resource_id: str,
        local_factory: LocalResourceFactory,
        date: datetime.datetime,
    ) -> Optional[Path]:
        """Synchronously download all matched files for one FetchResult."""
     

        hostname = query.server.hostname
     

        destination_resource = local_factory.sink_product(query.product, local_resource_id, date)
        destination_dir = Path(destination_resource.server.hostname) / destination_resource.directory.value  # type: ignore[union-attr]
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination_path = destination_dir / query.product.filename.value  # type: ignore[union-attr]
        protocol = (query.server.protocol or "").upper()
        adapter: Optional[Union[FTPAdapter,HTTPAdapter,LocalAdapter,DirectoryAdapter]] = self._adapters.get(protocol)
        if adapter is None:
            logger.error(f"Unsupported protocol for download: {protocol!r}")
            return None
        
        try:
            return adapter.download_file(
                hostname=hostname,
                directory=query.directory.value,  # type: ignore[union-attr]
                filename=query.product.filename.value,
                dest_path=destination_path,
            )
        except Exception as e:
            logger.error(f"Download failed for {hostname}/{query.directory.value}/{query.product.filename.value}: {e}")
            return None