"""Local filesystem directory adapter."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


class LocalAdapter:
    """DirectoryAdapter for local filesystem paths."""

    def can_connect(self, hostname: str) -> bool:
        return Path(hostname).exists()

    def list_directory(self, hostname: str, directory: str) -> List[str]:
        d = Path(hostname) / directory
        if not d.exists():
            return []
        return [p.name for p in sorted(d.iterdir()) if p.is_file()]

    def download_file(
        self, hostname: str, directory: str, filename: str, dest_path: Path
    ) -> bool:
        # Local files don't need downloading
        return False
