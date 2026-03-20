import logging
import re
from contextlib import contextmanager
from ftplib import FTP, FTP_TLS
from pathlib import Path
from typing import Generator, List

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
            logger.warning(f"{label} connection failed for {ftpserver} | {e}")
            last_exc = e
            if ftp is not None:
                try:
                    ftp.quit()
                except Exception:
                    pass
            ftp = None
            continue

    if ftp is None:
        raise ConnectionError(
            f"All FTP connection attempts failed for {ftpserver}"
        ) from last_exc

    try:
        yield ftp
    finally:
        try:
            ftp.quit()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def ftp_can_connect(
    ftpserver: str, timeout: int = 10, use_tls: bool = False
) -> bool:
    """Return True if an FTP login succeeds on *ftpserver*."""
    try:
        with _ftp_connect(ftpserver, timeout=timeout, use_tls=use_tls):
            logger.info(f"Successfully connected to {ftpserver}")
            return True
    except ConnectionError:
        return False


def ftp_list_directory(
    ftpserver: str,
    directory: str,
    timeout: int = 60,
    use_tls: bool = False,
) -> list[str]:
    """
    Connect to *ftpserver*, change to *directory*, and return the file listing.

    If *use_tls* is ``True``, only tries TLS.  Otherwise tries plain FTP
    first and retries with TLS on failure.

    Returns an empty list on any connection or command error so the caller
    can decide how to handle the failure.
    """
    try:
        with _ftp_connect(ftpserver, timeout=timeout, use_tls=use_tls) as ftp:
            ftp.cwd("/" + directory.strip("/"))
            return ftp.nlst()
    except ConnectionError:
        return []
    except Exception as e:  # noqa: BLE001
        logger.error(f"FTP listing failed for {directory} on {ftpserver}: {e}")
        return []


def ftp_download_file(
    ftpserver: str,
    directory: str,
    filename: str,
    dest_path: Path,
    timeout: int = 180,
    use_tls: bool = False,
) -> bool:
    """
    Download *filename* from *ftpserver*/*directory* to *dest_path*.

    Parent directories are created automatically.  Returns *True* on success
    (file exists and is non-empty), *False* on any failure (partial download
    is deleted before returning).

    If *use_tls* is ``False``, tries plain FTP first and automatically
    retries with TLS on failure.
    """
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with _ftp_connect(ftpserver, timeout=timeout, use_tls=use_tls) as ftp:
            ftp.cwd("/" + directory.strip("/"))
            with open(dest_path, "wb") as f:
                ftp.retrbinary(f"RETR {filename}", f.write)
            if dest_path.exists() and dest_path.stat().st_size > 0:
                return True
            dest_path.unlink(missing_ok=True)
            return False
    except ConnectionError:
        dest_path.unlink(missing_ok=True)
        return False
    except Exception as e:  # noqa: BLE001
        logger.error(f"FTP download failed for {filename} on {ftpserver}: {e}")
        dest_path.unlink(missing_ok=True)
        return False


def ftp_find_best_match_in_listing(
    dir_listing: list[str],
    file_regex: str,
) -> Generator[str, None, None]:
    """
    Yield entries from *dir_listing* that match *file_regex*.
    """
    pattern = re.compile(file_regex)
    for entry in dir_listing:
        if pattern.search(entry):
            yield entry


def ftp_protocol(
    ftpserver: str,
    directory: str,
    filename: str,
    use_tls: bool = False,
) -> List[str]:
    try:
        listing = ftp_list_directory(ftpserver, directory, use_tls=use_tls)
    except Exception as e:
        logger.error(f"Error listing FTP directory {ftpserver}/{directory}: {e}")
        return []
    matches = list(ftp_find_best_match_in_listing(listing, filename))
    if not matches:
        logger.warning(
            f"No matches found for {filename} in FTP directory {ftpserver}/{directory}"
        )
    return matches
