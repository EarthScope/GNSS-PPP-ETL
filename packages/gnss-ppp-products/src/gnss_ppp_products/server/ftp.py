import datetime
from ftplib import FTP, FTP_TLS
from pathlib import Path
import re
from typing import Generator, List, Optional, Tuple
import julian
from functools import lru_cache
import logging
logger = logging.getLogger(__name__)

def ftp_can_connect(ftpserver,timeout:int=10,use_tls:bool=False) -> bool:
    clean = ftpserver.replace("ftp://", "")
    try:
        if use_tls:
            ftp = FTP_TLS(clean, timeout=timeout)
            ftp.set_pasv(True)
            ftp.login()
            ftp.prot_p()  # Switch to secure data connection
        else:
            ftp = FTP(clean, timeout=timeout)
            ftp.set_pasv(True)
            ftp.login()
        with ftp:
            ftp.cwd("/")
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

    Returns an empty list on any connection or command error so the caller
    can decide how to handle the failure.
    
    Args:
        use_tls: If True, use FTPS (FTP over TLS) for servers requiring encryption
                 (e.g., NASA CDDIS requires TLS for anonymous sessions).
    """
    clean = ftpserver.replace("ftp://", "")
    try:
        if use_tls:
            ftp = FTP_TLS(clean, timeout=timeout)
            ftp.set_pasv(True)
            ftp.login()
            ftp.prot_p()  # Switch to secure data connection
        else:
            ftp = FTP(clean, timeout=timeout)
            ftp.set_pasv(True)
            ftp.login()
        with ftp:
            ftp.cwd("/" + directory)
            return ftp.nlst()
    except Exception as e:  # noqa: BLE001
        logger.error(f"Failed to list directory {directory} on {ftpserver} | {e}")
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
    
    Args:
        use_tls: If True, use FTPS (FTP over TLS) for servers requiring encryption
                 (e.g., NASA CDDIS requires TLS for anonymous sessions).
    """
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    clean = ftpserver.replace("ftp://", "")
    try:
        if use_tls:
            ftp = FTP_TLS(clean, timeout=timeout)
            ftp.set_pasv(True)
            ftp.login()
            ftp.prot_p()  # Switch to secure data connection
        else:
            ftp = FTP(clean, timeout=timeout)
            ftp.set_pasv(True)
            ftp.login()
        with ftp:
            ftp.cwd("/" + directory)
            with open(dest_path, "wb") as fh:
                ftp.retrbinary(f"RETR {filename}", fh.write)
        if dest_path.exists() and dest_path.stat().st_size > 0:
            return True
        dest_path.unlink(missing_ok=True)
        return False
    except Exception:  # noqa: BLE001
        dest_path.unlink(missing_ok=True)
        return False

def ftp_find_best_match_in_listing(
    dir_listing: list[str],
    file_regex: str,
) -> Generator [str, None, None]:
    """
    Search *dir_listing* with *file_regex* and return the first match, or
    *None* if nothing matches.
    """
    pattern = re.compile(file_regex)
    for entry in dir_listing:
        if pattern.search(entry):
            yield entry
    return None

def ftp_protocol(
    ftpserver: str,
    directory: str,
    filename: str,
    use_tls: bool = False
) -> List[str]:
        try:
            listing = ftp_list_directory(ftpserver, directory, use_tls=use_tls)
        except Exception as e:
            print(f"Error listing FTP directory {ftpserver}/{directory}: {e}")
            return []
        matches = list(ftp_find_best_match_in_listing(listing, filename))
        if not matches:
            print(f"No matches found for {filename} in FTP directory {ftpserver}/{directory}")
        return matches