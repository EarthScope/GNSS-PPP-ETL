"""Protocol adapter interface for directory listing and file download."""

from __future__ import annotations

from pathlib import Path
from typing import List, Protocol, runtime_checkable


@runtime_checkable
class DirectoryAdapter(Protocol):
    """Uniform contract for listing remote/local directories and downloading files.

    Implementations live in Layer 0 (``server/``).  The ``ResourceFetcher``
    in Layer 3 consumes adapters through this interface.
    """

    def can_connect(self, hostname: str) -> bool:
        """Return *True* if the host is reachable."""
        ...

    def list_directory(self, hostname: str, directory: str) -> List[str]:
        """Return filenames in *directory* on *hostname*."""
        ...

    def download_file(
        self,
        hostname: str,
        directory: str,
        filename: str,
        dest_path: Path,
    ) -> bool:
        """Download *filename* to *dest_path*.  Return *True* on success."""
        ...
