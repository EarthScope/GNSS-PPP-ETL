"""ResourceFetcher — protocol-agnostic file search and download."""

import asyncio
import datetime
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from gnss_ppp_products.server.ftp import ftp_can_connect, ftp_list_directory, ftp_download_file
from gnss_ppp_products.server.http import http_list_directory, extract_filenames_from_html, http_get_file
from gnss_ppp_products.specifications.products.product import ProductPath
from gnss_ppp_products.specifications.remote.resource import ResourceQuery
from gnss_ppp_products.specifications.local.factory import LocalResourceFactory

logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    """Outcome of searching one ResourceQuery against its server."""

    query: ResourceQuery
    matched_filenames: List[str] = field(default_factory=list)
    directory_listing: List[str] = field(default_factory=list)
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
            try:
                if protocol in ("FTP", "FTPS"):
                    listing = self._list_ftp(hostname, directory, use_tls=(protocol == "FTPS"))
                elif protocol in ("HTTP", "HTTPS"):
                    listing = self._list_http(hostname, directory)
                elif protocol in ("FILE", "LOCAL", ""):
                    listing = self._list_local(hostname, directory)
                else:
                    return FetchResult(query=query, error=f"Unsupported protocol: {protocol!r}")
                if not listing:
                    raise Exception("Listing returned empty")
            except Exception as e:
                return FetchResult(query=query, error=f"Listing failed: {e}")
            # Cache non-local listings
            if protocol not in ("FILE", "LOCAL", ""):
                self._listing_cache[cache_key] = listing

        matches = self._match_files(listing, file_pattern)

        if matches:
            self._resolve_values(query, directory, matches[0])

        return FetchResult(
            query=query,
            matched_filenames=matches,
            directory_listing=listing,
        )

    # -- Protocol handlers -----------------------------------------

    def _list_ftp(self, hostname: str, directory: str, *, use_tls: bool = False) -> List[str]:
        conn_key = f"{'ftps' if use_tls else 'ftp'}://{hostname}"
        if conn_key in self._connectivity_cache:
            if not self._connectivity_cache[conn_key]:
                raise ConnectionError(f"Server unreachable (cached): {hostname}")
        else:
            reachable = ftp_can_connect(hostname, timeout=self._ftp_timeout, use_tls=use_tls)
            self._connectivity_cache[conn_key] = reachable
            if not reachable:
                raise ConnectionError(f"Server unreachable: {hostname}")
        return ftp_list_directory(hostname, directory, timeout=self._ftp_timeout, use_tls=use_tls)

    def _list_http(self, hostname: str, directory: str) -> List[str]:
        html = http_list_directory(hostname, directory)
        if html is None:
            return []
        return extract_filenames_from_html(html)

    def _list_local(self, hostname: str, directory: str) -> List[str]:
        d = Path(hostname) / directory
        if not d.exists():
            return []
        return [p.name for p in sorted(d.iterdir()) if p.is_file()]

    # -- Pattern matching ------------------------------------------

    @staticmethod
    def _match_files(listing: List[str], file_pattern: str) -> List[str]:
        """Match filenames in a directory listing against a regex pattern."""
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
        results: List[FetchResult],
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
                loop.run_in_executor(pool, self._download_one, fr, local_factory, date)
                for fr in remote_found
            ]
            await asyncio.gather(*tasks)

        return results

    def _download_one(
        self,
        result: FetchResult,
        local_factory: LocalResourceFactory,
        date: datetime.datetime,
    ) -> None:
        """Synchronously download all matched files for one FetchResult."""
        query = result.query
        protocol = (query.server.protocol or "").upper()
        hostname = query.server.hostname
        directory = self._get_directory(query) or ""

        dest_dir = local_factory.resolve_directory(query.product.name, date)
        dest_dir.mkdir(parents=True, exist_ok=True)

        for filename in result.matched_filenames:
            dest_path = dest_dir / filename
            if dest_path.exists():
                logger.info(f"Already exists, skipping: {dest_path}")
                continue

            ok = False
            try:
                if protocol in ("FTP", "FTPS"):
                    ok = ftp_download_file(
                        hostname,
                        directory,
                        filename,
                        dest_path,
                        timeout=self._download_timeout,
                        use_tls=(protocol == "FTPS"),
                    )
                elif protocol in ("HTTP", "HTTPS"):
                    result_path = http_get_file(
                        hostname,
                        directory,
                        filename,
                        dest_dir=dest_dir,
                        timeout=self._download_timeout,
                    )
                    ok = result_path is not None
            except Exception as e:
                logger.error(f"Download failed for {filename}: {e}")

            if ok:
                result.download_dest = dest_dir
                logger.info(f"Downloaded {filename} → {dest_path}")
            else:
                logger.warning(f"Failed to download {filename} from {hostname}")
