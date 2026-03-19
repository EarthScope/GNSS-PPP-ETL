import logging
import re
from ftplib import FTP, FTP_TLS
from functools import lru_cache
from pathlib import Path
from typing import Generator, List

from fsspec.implementations.ftp import FTPFileSystem

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# FTPS (FTP over TLS) — needed for servers like NASA CDDIS
# ---------------------------------------------------------------------------


class FTPSFileSystem(FTPFileSystem):
    """fsspec FTP filesystem that uses TLS (``FTP_TLS``)."""

    protocol = "ftps"

    def _connect(self):
        if self.ftp is not None:
            return
        self.ftp = FTP_TLS(timeout=self.timeout)
        self.ftp.connect(self.host, self.port)
        self.ftp.login(self.username, self.password)
        self.ftp.prot_p()  # switch to secure data connection


def _open_fs(
    ftpserver: str, timeout: int = 60, use_tls: bool = False
) -> FTPFileSystem:
    """Return an ``FTPFileSystem`` (or ``FTPSFileSystem``) for *ftpserver*."""
    host = ftpserver.replace("ftp://", "").replace("ftps://", "").rstrip("/")
    cls = FTPSFileSystem if use_tls else FTPFileSystem
    return cls(host=host, port=21, timeout=timeout)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def ftp_can_connect(
    ftpserver: str, timeout: int = 10, use_tls: bool = False
) -> bool:
    try:
        fs = _open_fs(ftpserver, timeout=timeout, use_tls=use_tls)
        fs.ls("/")
        return True
    except Exception as e:  # noqa: BLE001
        logger.error(f"Failed to connect to FTP server {ftpserver} | {e}")
        return False

@lru_cache(maxsize=128)
def ftp_list_directory(
    ftpserver: str,
    directory: str,
    timeout: int = 60,
    use_tls: bool = False,
) -> list[str]:
    """
    Connect to *ftpserver*, change to *directory*, and return the file listing.

    If *use_tls* is ``False``, tries plain FTP first and automatically
    retries with TLS on failure.  If *use_tls* is ``True``, only tries TLS.

    Returns an empty list on any connection or command error so the caller
    can decide how to handle the failure.
    """
    clean = ftpserver.replace("ftp://", "").replace("ftps://", "").rstrip("/")

    for ftp_cls in [FTP, FTP_TLS]:
        try:
            with ftp_cls(clean, timeout=timeout) as ftp:
                ftp.set_pasv(True)
                ftp.login()
                if ftp_cls is FTP_TLS:
                    ftp.prot_p()  # switch data channel to TLS
                 
                ftp.cwd("/" + directory.strip("/"))
                entries = ftp.nlst()
                
                return entries
        except Exception as e:  # noqa: BLE001
            label = "FTPS" if ftp_cls is FTP_TLS else "FTP"
            logger.warning(f"{label} listing failed for {directory} on {ftpserver} | {e}")
            continue

    logger.error(f"All FTP attempts failed for {directory} on {ftpserver}")
    return []


# @lru_cache(maxsize=128)
# def ftp_list_directory(
#     ftpserver: str,
#     directory: str,
#     timeout: int = 60,
#     use_tls: bool = False,
# ) -> list[str]:
#     """
#     Connect to *ftpserver*, list *directory*, and return basenames.

#     Returns an empty list on any connection or command error so the caller
#     can decide how to handle the failure.

#     Args:
#         use_tls: If True, use FTPS (FTP over TLS) for servers requiring
#                  encryption (e.g., NASA CDDIS).
#     """
#     try:
#         # fs = _open_fs(ftpserver, timeout=timeout, use_tls=use_tls)
#         # entries = fs.ls("/" + directory, detail=False)
#         # # fs.ls returns full paths — strip to basenames
#         # return [e.rsplit("/", 1)[-1] for e in entries]
#         host = ftpserver.replace("ftp://", "").replace("ftps://", "").rstrip("/")
#         ftp = FTP(host, timeout=timeout)
#         ftp.login()
#         ftp.cwd("/" + directory.strip("/"))
#         return ftp.nlst()
#     except Exception as e:  # noqa: BLE001
#         logger.error(f"Failed to list directory {directory} on {ftpserver} | {e}")
#         return []


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
    tls_options = [use_tls] if use_tls else [False, True]

    for tls in tls_options:
        try:
            fs = _open_fs(ftpserver, timeout=timeout, use_tls=tls)
            remote = "/" + directory.strip("/") + "/" + filename
            fs.get(remote, str(dest_path))
            if dest_path.exists() and dest_path.stat().st_size > 0:
                if tls and not use_tls:
                    logger.info(f"Plain FTP download failed for {ftpserver}, succeeded with TLS")
                return True
            dest_path.unlink(missing_ok=True)
        except Exception as e:  # noqa: BLE001
            label = "FTPS" if tls else "FTP"
            logger.warning(f"{label} download failed for {filename} on {ftpserver} | {e}")
            dest_path.unlink(missing_ok=True)
            continue

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
