"""Author: Franklyn Dunbar

FTP / FTPS directory adapter and helper functions.

Provides both standalone functions (``ftp_can_connect``, ``ftp_list_directory``,
``ftp_download_file``) and a :class:`FTPAdapter` that implements the
:class:`DirectoryAdapter` protocol.
"""

import logging
import re
from collections.abc import Generator
from contextlib import contextmanager
from ftplib import FTP, FTP_TLS
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal connection helper
# ---------------------------------------------------------------------------


@contextmanager
def _ftp_connect(ftpserver: str, timeout: int = 60, use_tls: bool = False):
    """Yield an authenticated FTP connection with automatic TLS fallback.

    Strips ``ftp://`` / ``ftps://`` prefixes from *ftpserver*.
    If *use_tls* is True only TLS is attempted; otherwise plain FTP is
    tried first with a TLS retry on failure.

    Raises :class:`ConnectionError` if every attempt fails.
    """
    clean = ftpserver.replace("ftp://", "").replace("ftps://", "").rstrip("/")
    ftp_classes = [FTP_TLS] if use_tls else [FTP, FTP_TLS]

    last_exc: Exception | None = None
    ftp = None

    for ftp_cls in ftp_classes:
        try:
            ftp = ftp_cls(clean, timeout=timeout)
            ftp.set_pasv(True)
            ftp.login()
            if ftp_cls is FTP_TLS:
                ftp.prot_p()
            break  # connected successfully
        except Exception as e:  # noqa: BLE001
            label = "FTPS" if ftp_cls is FTP_TLS else "FTP"
            logger.warning("%s connection failed for %s | %s", label, ftpserver, e)
            last_exc = e
            if ftp is not None:
                try:
                    ftp.close()
                except Exception:
                    pass
            ftp = None
            continue

    if ftp is None:
        raise ConnectionError(f"All FTP connection attempts failed for {ftpserver}") from last_exc

    try:
        yield ftp
    finally:
        try:
            ftp.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def ftp_can_connect(ftpserver: str, timeout: int = 10, use_tls: bool = False) -> bool:
    """Return ``True`` if an FTP login succeeds on *ftpserver*.

    Args:
        ftpserver: FTP server address.
        timeout: Connection timeout in seconds.
        use_tls: If ``True``, only attempt FTPS.

    Returns:
        ``True`` on successful login, ``False`` otherwise.
    """
    try:
        with _ftp_connect(ftpserver, timeout=timeout, use_tls=use_tls):
            logger.debug("Successfully connected to %s", ftpserver)
            return True
    except ConnectionError:
        return False


def ftp_list_directory(
    ftpserver: str,
    directory: str,
    timeout: int = 60,
    use_tls: bool = False,
) -> list[str]:
    """Connect to *ftpserver*, ``CWD`` to *directory*, and return the file listing.

    Args:
        ftpserver: FTP server address.
        directory: Remote directory path.
        timeout: Connection timeout in seconds.
        use_tls: If ``True``, only attempt FTPS.

    Returns:
        A list of filenames, or an empty list on any connection or
        command error.
    """
    try:
        with _ftp_connect(ftpserver, timeout=timeout, use_tls=use_tls) as ftp:
            ftp.cwd("/" + directory.strip("/"))
            return ftp.nlst()
    except ConnectionError:
        return []
    except Exception as e:  # noqa: BLE001
        logger.warning("FTP listing failed for %s on %s: %s", directory, ftpserver, e)
        return []


def ftp_download_file(
    ftpserver: str,
    directory: str,
    filename: str,
    dest_path: Path,
    timeout: int = 180,
    use_tls: bool = False,
) -> Path | None:
    """Download *filename* from *ftpserver*/*directory* to *dest_path*.

    Parent directories are created automatically.  Partial downloads are
    deleted before returning.

    Args:
        ftpserver: FTP server address.
        directory: Remote directory path.
        filename: Name of the file to retrieve.
        dest_path: Local destination path.
        timeout: Connection timeout in seconds.
        use_tls: If ``True``, only attempt FTPS.

    Returns:
        The path to the downloaded file on success (file exists and is
        non-empty), or ``None`` on any failure.
    """
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with _ftp_connect(ftpserver, timeout=timeout, use_tls=use_tls) as ftp:
            ftp.cwd("/" + directory.strip("/"))
            with open(dest_path, "wb") as f:
                ftp.retrbinary(f"RETR {filename}", f.write)
            if dest_path.exists() and dest_path.stat().st_size > 0:
                return dest_path
            dest_path.unlink(missing_ok=True)
            return None
    except ConnectionError:
        dest_path.unlink(missing_ok=True)
        return None
    except Exception as e:  # noqa: BLE001
        logger.warning("FTP download failed for %s on %s: %s", filename, ftpserver, e)
        dest_path.unlink(missing_ok=True)
        return None


def ftp_find_best_match_in_listing(
    dir_listing: list[str],
    file_regex: str,
) -> Generator[str, None, None]:
    """Yield entries from *dir_listing* that match *file_regex*.

    Args:
        dir_listing: List of filenames from a directory listing.
        file_regex: Regular expression to match against entries.

    Yields:
        Filenames that match *file_regex*.
    """
    pattern = re.compile(file_regex)
    for entry in dir_listing:
        if pattern.search(entry):
            yield entry


# ---------------------------------------------------------------------------
# DirectoryAdapter implementation
# ---------------------------------------------------------------------------


class FTPAdapter:
    """DirectoryAdapter for FTP/FTPS servers.

    Args:
        timeout: Default timeout in seconds for FTP operations.
        use_tls: If ``True``, only attempt FTPS connections.
    """

    def __init__(self, *, timeout: int = 60, use_tls: bool = False) -> None:
        self._timeout = timeout
        self._use_tls = use_tls

    def can_connect(self, hostname: str) -> bool:
        """Test FTP/FTPS connectivity to *hostname*."""
        return ftp_can_connect(hostname, timeout=min(self._timeout, 10), use_tls=self._use_tls)

    def list_directory(self, hostname: str, directory: str) -> list[str]:
        """List filenames in a remote FTP directory."""
        return ftp_list_directory(hostname, directory, timeout=self._timeout, use_tls=self._use_tls)

    def download_file(
        self, hostname: str, directory: str, filename: str, dest_path: Path
    ) -> Path | None:
        """Download a file from an FTP server to *dest_path*."""
        return ftp_download_file(
            hostname,
            directory,
            filename,
            dest_path,
            timeout=self._timeout * 3,
            use_tls=self._use_tls,
        )
