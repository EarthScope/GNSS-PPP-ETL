"""Author: Franklyn Dunbar

Server protocol adapters for FTP, HTTP, and local filesystem access.

Public API:
    - :class:`DirectoryAdapter` -- protocol interface
    - :class:`FTPAdapter` -- FTP / FTPS
    - :class:`HTTPAdapter` -- HTTP / HTTPS
    - :class:`LocalAdapter` -- local filesystem
"""

from .ftp import (
    FTPAdapter as FTPAdapter,
)
from .ftp import (
    ftp_can_connect as ftp_can_connect,
)
from .ftp import (
    ftp_download_file as ftp_download_file,
)
from .ftp import (
    ftp_find_best_match_in_listing as ftp_find_best_match_in_listing,
)
from .ftp import (
    ftp_list_directory as ftp_list_directory,
)
from .http import (
    HTTPAdapter as HTTPAdapter,
)
from .http import (
    extract_filenames_from_html as extract_filenames_from_html,
)
from .http import (
    http_list_directory as http_list_directory,
)
from .local import LocalAdapter as LocalAdapter
from .protocol import DirectoryAdapter as DirectoryAdapter
