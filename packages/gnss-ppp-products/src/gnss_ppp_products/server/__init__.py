"""Author: Franklyn Dunbar

Server protocol adapters for FTP, HTTP, and local filesystem access.

Public API:
    - :class:`DirectoryAdapter` -- protocol interface
    - :class:`FTPAdapter` -- FTP / FTPS
    - :class:`HTTPAdapter` -- HTTP / HTTPS
    - :class:`LocalAdapter` -- local filesystem
"""

from .ftp import (
    ftp_can_connect,
    ftp_list_directory,
    ftp_download_file,
    ftp_find_best_match_in_listing,
    FTPAdapter,
)
from .http import extract_filenames_from_html, http_list_directory, HTTPAdapter
from .local import LocalAdapter
from .protocol import DirectoryAdapter
