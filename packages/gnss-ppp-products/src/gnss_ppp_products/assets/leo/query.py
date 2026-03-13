from enum import Enum
from typing import Optional

from ..utils import parse_date
from ..server import Server
from .base import LEOBase, GRACEMission, GRACEInstrument, _RegexFallbackDict


class LEOFileQuery(LEOBase):
    server: Optional[Server] = None

    def _substitution_map(self) -> dict[str, str]:
        """Collect known field values as a ``{placeholder: value}`` mapping."""
        subs: dict[str, str] = {}
        if self.date is not None:
            year, doy = parse_date(self.date)
            subs["year"] = year
            subs["doy"] = doy
            subs["month"] = f"{self.date.month:02d}"
            subs["day"] = f"{self.date.day:02d}"
        if self.mission is not None:
            subs["mission"] = self.mission.value if isinstance(self.mission, Enum) else self.mission
        if self.instrument is not None:
            val = self.instrument.value if isinstance(self.instrument, Enum) else self.instrument
            subs["instrument"] = f"{val}1B"
        return subs

    def build_filename(self, template: str) -> None:
        self.filename = template.format_map(_RegexFallbackDict(self._substitution_map()))

    def build_directory(self, template: str) -> None:
        self.directory = template.format_map(_RegexFallbackDict(self._substitution_map()))
