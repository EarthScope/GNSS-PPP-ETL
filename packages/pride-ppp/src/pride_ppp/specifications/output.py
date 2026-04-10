"""
PRIDE-PPP kinematic position model.

Provides the ``PridePPP`` Pydantic model for individual kinematic records
parsed from pdp3 ``.kin`` output files.
"""

import logging
from datetime import datetime
from typing import List, Optional, Union

import julian
from pydantic import BaseModel, Field, ValidationError, model_validator

logger = logging.getLogger(__name__)

#: Column-index → field-name mapping for PRIDE-PPPAR ``.kin`` output lines.
#: The pdp3 binary writes fixed-width records; this dict maps positional
#: token indices (after whitespace-split) to the corresponding field names
#: used by ``PridePPP``.
PRIDE_PPP_LOG_INDEX = {
    0: "modified_julian_date",
    1: "second_of_day",
    2: "east",
    3: "north",
    4: "up",
    5: "latitude",
    6: "longitude",
    7: "height",
    8: "number_of_satellites",
    9: "pdop",
}


class PridePPP(BaseModel):
    """Single-epoch kinematic position record from a pdp3 ``.kin`` file.

    Each instance represents one line of output.  Coordinates are in a
    local East/North/Up frame (metres) plus geodetic lat/lon/height.

    Attributes
    ----------
    modified_julian_date : float
        Modified Julian Date of the epoch (≥ 0).
    second_of_day : float
        Seconds elapsed since midnight UTC (0–86 400).
    east : float
        East displacement in metres (local ENU frame).
    north : float
        North displacement in metres (local ENU frame).
    up : float
        Up displacement in metres (local ENU frame).
    latitude : float
        Geodetic latitude in decimal degrees (−90–90).
    longitude : float
        Geodetic longitude in decimal degrees (0–360, east-positive).
    height : float
        WGS-84 ellipsoidal height in metres.
    number_of_satellites : int
        Number of satellites used in the solution.
    pdop : float
        Position Dilution of Precision.
    time : datetime, optional
        UTC timestamp derived from ``modified_julian_date`` and
        ``second_of_day`` (populated automatically by a validator).

    Docs: https://github.com/PrideLab/PRIDE-PPPAR
    """

    modified_julian_date: float = Field(ge=0)
    second_of_day: float = Field(ge=0, le=86400)
    east: float = Field(ge=-6378100, le=6378100)
    north: float = Field(ge=-6378100, le=6378100)
    up: float = Field(ge=-6378100, le=6378100)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=0, le=360)
    height: float = Field(ge=-1000, le=10000)
    number_of_satellites: int = Field(default=1, ge=0, le=125)
    pdop: float = Field(default=0, ge=0, le=1000)
    time: Optional[datetime] = None

    class Config:
        coerce = True

    @model_validator(mode="before")
    def validate_time(cls, values):
        """Coerce ``pdop`` to float before full field validation.

        Some ``.kin`` files encode PDOP as an integer string.  This
        pre-validator ensures it is always a float so the ``ge``/``le``
        constraints pass.
        """
        values["pdop"] = float(values.get("pdop", 0.0))
        return values

    @model_validator(mode="after")
    def populate_time(cls, values):
        """Derive UTC ``time`` from MJD and second-of-day.

        Converts ``modified_julian_date`` + ``second_of_day`` to a full
        Julian Date, then to a Python ``datetime`` via the ``julian``
        library.
        """
        julian_date = (
            values.modified_julian_date + (values.second_of_day / 86400) + 2400000.5
        )
        t = julian.from_jd(julian_date, fmt="jd")
        values.time = t
        return values

    @classmethod
    def from_kin_file(cls, data: List[str]) -> Union["PridePPP", ValidationError]:
        """Parse a single line (as split tokens) from a ``.kin`` file.

        Parameters
        ----------
        data : List[str]
            A list of strings representing a line from the kin file.

        Returns
        -------
        Union["PridePPP", ValidationError]
            A PridePPP object or a validation error.
        """
        try:
            data_dict = {}
            if "*" in data:
                data.remove("*")
            if len(data) < 10:
                data.insert(-1, 1)  # account for missing number of satellites
            for i, item in enumerate(data):
                field = PRIDE_PPP_LOG_INDEX[i]
                data_dict[field] = item
            return cls(**data_dict)
        except ValidationError as e:
            raise Exception(f"Error parsing PridePPP kin file {e}")
