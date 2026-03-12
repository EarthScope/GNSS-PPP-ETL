from enum import Enum
from typing import Optional

from ..utils import parse_date
from ..server import Server
from .base import TroposphereBase, VMFProduct, VMFHour, _RegexFallbackDict


class TroposphereFileQuery(TroposphereBase):
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
        if self.product is not None:
            # VMF1 uses "VMFG" in filenames, VMF3 uses "VMF3"
            val = self.product.value if isinstance(self.product, Enum) else self.product
            subs["product"] = "VMFG" if val == "VMF1" else val
        if self.resolution is not None:
            subs["resolution"] = self.resolution.value if isinstance(self.resolution, Enum) else self.resolution
        if self.hour is not None:
            subs["hh"] = self.hour.value if isinstance(self.hour, Enum) else self.hour
        return subs

    def build_filename(self, template: str) -> None:
        self.filename = template.format_map(_RegexFallbackDict(self._substitution_map()))

    def build_directory(self, template: str) -> None:
        self.directory = template.format_map(_RegexFallbackDict(self._substitution_map()))
