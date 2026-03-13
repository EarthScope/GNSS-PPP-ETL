import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import List, Optional
from urllib.parse import unquote

import fsspec

logger = logging.getLogger(__name__)


def _open_http(server: str) -> fsspec.AbstractFileSystem:
    """Return an fsspec HTTP(S) filesystem."""
    protocol = "https" if server.startswith("https") else "http"
    return fsspec.filesystem(protocol)


def http_can_connect(httpserver: str, timeout: int = 10) -> bool:
    try:
        fs = _open_http(httpserver)
        fs.info(httpserver)
        return True
    except Exception as e:  # noqa: BLE001
        logger.error(f"Failed to connect to HTTP server {httpserver} | {e}")
        return False


def extract_filenames_from_html(html: str) -> list[str]:
    """
    Extract filenames from an Apache/nginx HTML directory listing.

    Parses ``<a href="filename">`` tags to get file names.
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
    """Fetch the raw HTML directory listing from *server*/*directory*."""
    try:
        url = f"{server}/{directory}"
        with fsspec.open(url, "r") as f:
            return f.read()
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error listing HTTP directory {server}/{directory}: {e}")
        return None


def http_protocol(
    httpserver: str,
    directory: str,
    filequery: str,
) -> List[str]:
    out = []
    listing: Optional[str] = http_list_directory(
        server=httpserver, directory=directory
    )
    if listing is None:
        return out
    for filename in extract_filenames_from_html(listing):
        if re.match(filequery, filename):
            logger.info(f"Match for {filequery}: {filename}")
            out.append(filename)
    return out


def http_get_file(
    httpserver: str,
    directory: str,
    filename: str,
    dest_dir: Optional[Path] = None,
    timeout: int = 60,
) -> Optional[Path]:
    """Download a file via HTTP(S) and return the local path, or *None* on failure."""
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
