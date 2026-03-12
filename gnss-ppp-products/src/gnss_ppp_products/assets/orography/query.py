from enum import Enum
from typing import Optional

from ..server import Server
from .base import OrographyBase, _RegexFallbackDict


class OrographyFileQuery(OrographyBase):
    """Query for an orography grid file. These are static (no date component)."""
    server: Optional[Server] = None

    def _substitution_map(self) -> dict[str, str]:
        """Collect known field values as a ``{placeholder: value}`` mapping."""
        subs: dict[str, str] = {}
        if self.resolution is not None:
            subs["resolution"] = self.resolution.value if isinstance(self.resolution, Enum) else self.resolution
        return subs

    def build_filename(self, template: str) -> None:
        self.filename = template.format_map(_RegexFallbackDict(self._substitution_map()))

    def build_directory(self, template: str) -> None:
        self.directory = template.format_map(_RegexFallbackDict(self._substitution_map()))
