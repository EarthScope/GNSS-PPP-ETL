from itertools import product
from typing import List, Optional
import datetime

from pydantic import BaseModel

from .base import LEOBase, GRACEMission, GRACEInstrument
from .query import LEOFileQuery


# ---------------------------------------------------------------------------
# YAML configuration schemas
# ---------------------------------------------------------------------------


class GRACEMissionConfig(BaseModel):
    mission: GRACEMission
    description: Optional[str] = None


class GRACEInstrumentConfig(BaseModel):
    instrument: GRACEInstrument
    description: Optional[str] = None


class LEOConfig(LEOBase):
    """Configuration for a LEO satellite (GRACE/GRACE-FO) product."""
    id: str
    server_id: str
    available: bool = True
    description: Optional[str] = None
    notes: Optional[str] = None
    mission_set: List[GRACEMissionConfig]
    instrument_set: List[GRACEInstrumentConfig]

    def build(self, date: datetime.datetime | datetime.date) -> List[LEOFileQuery]:
        """Expand config into all combinations of mission/instrument."""
        assert self.filename is not None, "LEOConfig must have a filename template"
        assert self.directory is not None, "LEOConfig must have a directory template"

        missions = [m.mission for m in self.mission_set] or [None]
        instruments = [i.instrument for i in self.instrument_set] or [None]

        queries: list[LEOFileQuery] = []
        for mission, instrument in product(missions, instruments):
            query = LEOFileQuery(
                date=date,
                mission=mission,
                instrument=instrument,
            )
            query.build_filename(self.filename)
            query.build_directory(self.directory)
            queries.append(query)
        return queries
