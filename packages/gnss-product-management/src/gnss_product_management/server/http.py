"""Author: Franklyn Dunbar

HTTP / HTTPS directory adapter and helper functions.

Provides standalone functions (``http_can_connect``, ``http_list_directory``,
``http_get_file``, ``extract_filenames_from_html``) and a :class:`HTTPAdapter`
that implements the :class:`DirectoryAdapter` protocol.
"""

import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import List, Optional
from urllib.parse import unquote

import fsspec

logger = logging.getLogger(__name__)


def _open_http(server: str) -> fsspec.AbstractFileSystem:
    """Return an fsspec HTTP(S) filesystem.

    Args:
        server: Server URL used to infer the protocol.

    Returns:
        An fsspec filesystem instance (``http`` or ``https``).
    """
    protocol = "https" if server.startswith("https") else "http"
    return fsspec.filesystem(protocol)


def http_can_connect(httpserver: str, timeout: int = 10) -> bool:
    """Return ``True`` if the HTTP server is reachable.

    Args:
        httpserver: Full server URL.
        timeout: Connection timeout in seconds.

    Returns:
        ``True`` on success, ``False`` otherwise.
    """
    try:
        fs = _open_http(httpserver)
        fs.info(httpserver)
        return True
    except Exception as e:  # noqa: BLE001
        logger.error(f"Failed to connect to HTTP server {httpserver} | {e}")
        return False


def extract_filenames_from_html(html: str) -> list[str]:
    """Extract filenames from an Apache/nginx HTML directory listing.

    Parses ``<a href="filename">`` tags, URL-decodes them, and filters
    out query-string and directory links.

    Args:
        html: Raw HTML string from a directory listing page.

    Returns:
        A list of decoded filenames.
    """
    pattern = r'<a href="([^"?/][^"?]*)"'
    matches = re.findall(pattern, html)
    filenames = []
    for match in matches:
        decoded = unquote(match)
        if decoded and not decoded.startswith("?") and not decoded.endswith("/"):
            filenames.append(decoded)
    return filenames


@lru_cache(maxsize=128)
def http_list_directory(server: str, directory: str) -> Optional[str]:
    """Fetch the raw HTML directory listing from *server*/*directory*.

    Args:
        server: Base URL of the HTTP server.
        directory: Directory path relative to the server root.

    Returns:
        The HTML body as a string, or ``None`` on error.
    """
    try:
        url = f"{server}/{directory}"
        with fsspec.open(url, "r") as f:
            return f.read()
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error listing HTTP directory {server}/{directory}: {e}")
        return None


def http_get_file(
    httpserver: str,
    directory: str,
    filename: str,
    dest_dir: Optional[Path] = None,
    timeout: int = 60,
) -> Optional[Path]:
    """Download a file via HTTP(S).

    Args:
        httpserver: Base URL of the HTTP server.
        directory: Directory path on the server.
        filename: Name of the file to download.
        dest_dir: Local directory for the download.  Defaults to CWD.
        timeout: Connection timeout in seconds.

    Returns:
        Path to the downloaded file, or ``None`` on failure.
    """
    try:
        fs = _open_http(httpserver)
        url = f"{httpserver}/{directory}/{filename}"
        if dest_dir is not None:
            dest_dir.mkdir(parents=True, exist_ok=True)
            file_path = dest_dir / filename
        else:
            file_path = Path(filename)
        fs.get(url, str(file_path))
        return file_path
    except Exception as e:  # noqa: BLE001
        logger.error(
            f"Error fetching HTTP file {httpserver}/{directory}/{filename}: {e}"
        )
        return None


# ---------------------------------------------------------------------------
# DirectoryAdapter implementation
# ---------------------------------------------------------------------------


class HTTPAdapter:
    """DirectoryAdapter for HTTP/HTTPS servers.

    Args:
        timeout: Default timeout in seconds.
    """

    def __init__(self, *, timeout: int = 60) -> None:
        self._timeout = timeout

    def can_connect(self, hostname: str) -> bool:
        """Test HTTP/HTTPS connectivity to *hostname*."""
        return http_can_connect(hostname, timeout=min(self._timeout, 10))

    def list_directory(self, hostname: str, directory: str) -> List[str]:
        """List filenames from an HTTP directory listing page."""
        html = http_list_directory(hostname, directory)
        if html is None:
            return []
        return extract_filenames_from_html(html)

    def download_file(
        self, hostname: str, directory: str, filename: str, dest_path: Path
    ) -> Optional[Path]:
        """Download a file from an HTTP server to *dest_path*."""
        result = http_get_file(
            hostname,
            directory,
            filename,
            dest_dir=dest_path.parent,
            timeout=self._timeout,
        )
        return result
