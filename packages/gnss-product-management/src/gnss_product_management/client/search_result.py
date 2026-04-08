"""Author: Franklyn Dunbar

SearchResult — public result type for GNSSClient.search().
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class SearchResult:
    """A resolved, ranked product candidate ready for download.

    Returned by :meth:`GNSSClient.search`.  Exposes only the fields a
    caller needs: server location, matched filename, and the parameters
    inferred from the filename.  Call :meth:`GNSSClient.download` with a
    list of these to fetch them to disk.

    Attributes:
        hostname: Server hostname (or local base directory for file results).
        protocol: Transport protocol (``ftp``, ``https``, ``file``, …).
        directory: Resolved remote or local directory path.
        filename: Matched filename.
        parameters: Product metadata parameters inferred from the filename.
        local_path: Set after a successful download; ``None`` beforehand.
    """

    hostname: str
    protocol: str
    directory: str
    filename: str
    parameters: Dict[str, str] = field(default_factory=dict)
    local_path: Optional[Path] = None
    # Internal — holds the SearchTarget for use by GNSSClient.download().
    # Not part of the public interface.
    _query: Any = field(default=None, repr=False, compare=False, init=False)

    @property
    def downloaded(self) -> bool:
        """``True`` if the file has been downloaded and exists on disk."""
        return self.local_path is not None and self.local_path.exists()
