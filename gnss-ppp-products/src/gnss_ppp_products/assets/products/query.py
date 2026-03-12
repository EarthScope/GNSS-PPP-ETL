from typing import Optional
import datetime

from ..utils import parse_date, date_to_gps_week
from ..server import Server
#from ..base import ProductCampaignSpec, ProductContentType, ProductDuration, ProductFileFormat, ProductSampleInterval, ProductSolutionType
from .base import (
    _RegexFallbackDict,
    ProductBase,AnalysisCenter,ProductCampaignSpec,ProductSolutionType,ProductSampleInterval,ProductDuration,ProductType,ProductFileFormat,ProductContentType,
)

class ProductFileQuery(ProductBase):
 
    server: Optional[Server] = None

    @classmethod
    def from_filename(cls, filename: str) -> "ProductFileQuery":
        center_solution, yeardoy, coverage, sample, content = filename.split("_")

        center = AnalysisCenter(center_solution[:3])
        version = center_solution[3]
        campaign = ProductCampaignSpec(center_solution[4:7])
        solution = ProductSolutionType(center_solution[7:])
        year = int(yeardoy[:4])
        doy = int(yeardoy[4:7])
        hour = int(yeardoy[7:9])
        minute = int(yeardoy[9:11])
        date = datetime.datetime(year, 1, 1) + datetime.timedelta(days=doy - 1, hours=hour, minutes=minute)
        duration = ProductDuration(coverage)
        interval = ProductSampleInterval(sample)
        content_type = ProductContentType(content.split(".")[0])
        file_format = ProductFileFormat(content.split(".")[1].split(".")[0])
        return cls(
            date=date,
            center=center,
            version=version,
            campaign=campaign,
            interval=interval,
            duration=duration,
            content=content_type,
            format=file_format,
            solution=solution,
            filename=filename,
        )

    # -- substitution helpers ------------------------------------------------

    def _substitution_map(self) -> dict[str, str]:
        """Collect known field values as a ``{placeholder: value}`` mapping."""
        subs: dict[str, str] = {}
        if self.date is not None:
            year, doy = parse_date(self.date)
            subs["year"] = year
            subs["doy"] = doy
            subs["gps_week"] = str(date_to_gps_week(self.date))
            subs["yy"] = str(self.date.year)[-2:]
            subs["month"] = f"{self.date.month:02d}"
            subs["day"] = f"{self.date.day:02d}"
        if self.center is not None:
            subs["center"] = self.center
        if self.version is not None:
            subs["version"] = self.version
        if self.campaign is not None:
            subs["campaign"] = self.campaign.value
        if self.solution is not None:
            subs["quality"] = self.solution.value if isinstance(self.solution, str) else self.solution.value
        if self.interval is not None:
            subs["interval"] = self.interval.value
        if self.duration is not None:
            subs["duration"] = self.duration.value
        if self.content is not None:
            subs["content"] = self.content.value
        if self.format is not None:
            subs["format"] = self.format.value
        return subs

    def build_filename(self, template: str) -> Optional[str]:
        """
        Build a filename pattern from a template string.

        Known field values are substituted literally; missing fields
        become regex patterns suitable for matching against directory
        listings.

        Parameters
        ----------
        template : str
            Filename template with ``{placeholder}`` tokens, e.g.
            ``"{center}{version}{campaign}{quality}_{year}{doy}0000_{duration}_{interval}_ORB.SP3.*"``

        Returns
        -------
        str
            Pattern string with all placeholders resolved.
        """
        self.filename = template.format_map(_RegexFallbackDict(self._substitution_map()))

    def build_directory(self, template: str) -> Optional[str]:
        """Build a directory path from a template, substituting known values."""
        self.directory = template.format_map(_RegexFallbackDict(self._substitution_map()))

