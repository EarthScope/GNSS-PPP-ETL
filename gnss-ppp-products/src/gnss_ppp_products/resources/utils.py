import datetime
from ftplib import FTP
from pathlib import Path
import re
from typing import Optional, Tuple


def _parse_date(date: datetime.date | datetime.datetime) -> Tuple[str, str]:
    """
    Parse a date or datetime object and return the year and day of year (DOY) as strings.
    Args:
        date (datetime.date | datetime.datetime): The date or datetime object to parse.
    Returns:
        Tuple[str, str]: A tuple containing the year and the day of year (DOY) as strings.
    """

    if isinstance(date, datetime.datetime):
        date = date.date()
    year = str(date.year)
    doy = date.timetuple().tm_yday
    if doy < 10:
        doy = f"00{doy}"
    elif doy < 100:
        doy = f"0{doy}"
    doy = str(doy)
    return year, doy


GNSS_START_TIME = datetime.datetime(
    1980, 1, 6, tzinfo=datetime.timezone.utc
)  # GNSS start time


def _date_to_gps_week(date: datetime.date | datetime.datetime) -> int:
    """
    Convert a given date to the corresponding GPS week number.

    The GPS week number is calculated as the number of weeks since the start of the GPS epoch (January 6, 1980).

    Args:
        date (datetime.date | datetime.datetime): The date to be converted. Can be either a datetime.date or datetime.datetime object.

    Returns:
        int: The GPS week number corresponding to the given date.
    """
    # get the number of weeks since the start of the GPS epoch

    if isinstance(date, datetime.datetime):
        date = date.date()
    time_since_epoch = date - GNSS_START_TIME.date()
    gps_week = time_since_epoch.days // 7
    return gps_week


def ftp_list_directory(
    ftpserver: str,
    directory: str,
    timeout: int = 60,
) -> list[str]:
    """
    Connect to *ftpserver*, change to *directory*, and return the file listing.

    Returns an empty list on any connection or command error so the caller
    can decide how to handle the failure.
    """
    clean = ftpserver.replace("ftp://", "")
    try:
        with FTP(clean, timeout=timeout) as ftp:
            ftp.set_pasv(True)
            ftp.login()
            ftp.cwd("/" + directory)
            return ftp.nlst()
    except Exception:  # noqa: BLE001
        return []


def ftp_download_file(
    ftpserver: str,
    directory: str,
    filename: str,
    dest_path: Path,
    timeout: int = 180,
) -> bool:
    """
    Download *filename* from *ftpserver*/*directory* to *dest_path*.

    Parent directories are created automatically.  Returns *True* on success
    (file exists and is non-empty), *False* on any failure (partial download
    is deleted before returning).
    """
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    clean = ftpserver.replace("ftp://", "")
    try:
        with FTP(clean, timeout=timeout) as ftp:
            ftp.set_pasv(True)
            ftp.login()
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


def find_best_match_in_listing(
    dir_listing: list[str],
    file_regex: str,
) -> Optional[str]:
    """
    Search *dir_listing* with *file_regex* and return the first match, or
    *None* if nothing matches.
    """
    pattern = re.compile(file_regex)
    for entry in dir_listing:
        if pattern.search(entry):
            return entry
    return None
