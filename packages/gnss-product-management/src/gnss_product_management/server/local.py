"""Author: Franklyn Dunbar

Local filesystem directory adapter.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class LocalAdapter:
    """DirectoryAdapter for local filesystem paths.

    Implements the :class:`DirectoryAdapter` protocol using :mod:`pathlib`
    so that local directories can be listed with the same interface
    used for FTP and HTTP servers.
    """

    def can_connect(self, hostname: str) -> bool:
        """Return ``True`` if *hostname* is an existing local directory."""
        return Path(hostname).exists()

    def list_directory(self, hostname: str, directory: str) -> list[str]:
        """List filenames in a local directory."""
        d = Path(hostname) / directory
        if not d.exists():
            return []
        return [p.name for p in sorted(d.iterdir()) if p.is_file()]

    def download_file(
        self, hostname: str, directory: str, filename: str, dest_path: Path
    ) -> Path | None:
        """No-op — local files do not require downloading."""
        return None
