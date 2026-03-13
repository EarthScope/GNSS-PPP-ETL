from typing import Optional

from ..server import Server
from .base import ReferenceTableBase, _RegexFallbackDict


class ReferenceTableFileQuery(ReferenceTableBase):
    """Query for a reference table file. These are static (no date component)."""
    server: Optional[Server] = None

    def _substitution_map(self) -> dict[str, str]:
        """Collect known field values as a ``{placeholder: value}`` mapping."""
        return {}

    def build_filename(self, template: str) -> None:
        self.filename = template.format_map(_RegexFallbackDict(self._substitution_map()))

    def build_directory(self, template: str) -> None:
        self.directory = template.format_map(_RegexFallbackDict(self._substitution_map()))
