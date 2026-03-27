"""
PRIDE-PPP kinematic output parsing and validation.

Provides the ``PridePPP`` Pydantic model for individual kinematic records,
plus helpers for reading ``.kin`` / ``.res`` files into DataFrames.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union

import julian
import pandas as pd
from pydantic import BaseModel, Field, ValidationError, model_validator

logger = logging.getLogger(__name__)

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
    """Data class for PPP GNSS kinematic position output.

    Docs: https://github.com/PrideLab/PRIDE-PPPAR
    """

    modified_julian_date: float = Field(ge=0)
    second_of_day: float = Field(ge=0, le=86400)
    east: float = Field(ge=-6378100, le=6378100)
    north: float = Field(ge=-6378100, le=6378100)
    up: float = Field(ge=-6378100, le=6378100)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=0, le=360)
    height: float = Field(ge=-101, le=100)
    number_of_satellites: int = Field(default=1, ge=0, le=125)
    pdop: float = Field(default=0, ge=0, le=1000)
    time: Optional[datetime] = None

    class Config:
        coerce = True

    @model_validator(mode="before")
    def validate_time(cls, values):
        values["pdop"] = float(values.get("pdop", 0.0))
        return values

    @model_validator(mode="after")
    def populate_time(cls, values):
        """Convert from modified julian date and seconds of day to standard datetime format."""
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


# ---------------------------------------------------------------------------
# RES file helpers
# ---------------------------------------------------------------------------


def get_wrms_from_res(res_path):
    """Get WRMS from a RES file.

    Parameters
    ----------
    res_path : str
        The path to the RES file.

    Returns
    -------
    pd.DataFrame
        A DataFrame with the WRMS data.
    """
    with open(res_path, "r") as res_file:
        timestamps = []
        data = []
        wrms = 0
        sumOfSquares = 0
        sumOfWeights = 0
        line = res_file.readline()  # first line is header

        while True:
            if line == "":
                break
            line_data = line.split()
            if line_data[0] == "TIM":
                sumOfSquares = 0
                sumOfWeights = 0

                seconds_str = line_data[6]
                if "." in seconds_str:
                    SS, fractional = seconds_str.split(".")
                    SS = int(SS)
                    fractional = fractional.ljust(6, "0")[:6]
                else:
                    SS = int(seconds_str)
                    fractional = "000000"

                isodate = (
                    f"{line_data[1]}-{line_data[2].zfill(2)}-{line_data[3].zfill(2)}"
                    f"T{line_data[4].zfill(2)}:{line_data[5].zfill(2)}:{str(SS).zfill(2)}"
                    f".{fractional}+00:00"
                )

                timestamp = datetime.fromisoformat(isodate)
                timestamps.append(timestamp)

                line = res_file.readline()
                line_data = line.split()
                while not line.startswith("TIM"):
                    phase_residual = float(line_data[1])
                    phase_weight = float(line_data[3].replace("D", "E"))
                    sumOfSquares += phase_residual**2 * phase_weight
                    sumOfWeights += phase_weight
                    line = res_file.readline()
                    if line == "":
                        break
                    line_data = line.split()
                wrms = (sumOfSquares / sumOfWeights) ** 0.5 * 1000  # in mm
                data.append(wrms)
            else:
                line = res_file.readline()

    wrms_df = pd.DataFrame({"date": timestamps, "wrms": data})
    return wrms_df


def plot_kin_results_wrms(kin_df, title=None, save_as=None):
    """Plot kinematic results with WRMS.

    Parameters
    ----------
    kin_df : pd.DataFrame
        The kinematic data.
    title : str, optional
        The title of the plot, by default None.
    save_as : str, optional
        The path to save the plot to, by default None.
    """
    import matplotlib.pyplot as plt

    size = 3
    bad_nsat = kin_df[kin_df["Nsat"] <= 4]
    bad_pdop = kin_df[kin_df["PDOP"] >= 5]
    fig, axs = plt.subplots(6, 1, figsize=(10, 10), sharex=True)
    axs[0].scatter(kin_df.index, kin_df["Latitude"], s=size)
    axs[0].set_ylabel("Latitude")
    axs[1].scatter(kin_df.index, kin_df["Longitude"], s=size)
    axs[1].set_ylabel("Longitude")
    axs[2].scatter(kin_df.index, kin_df["Height"], s=size)
    axs[2].set_ylabel("Height")
    axs[3].scatter(kin_df.index, kin_df["Nsat"], s=size)
    axs[3].scatter(bad_nsat.index, bad_nsat["Nsat"], s=size * 2, color="red")
    axs[3].set_ylabel("Nsat")
    axs[4].scatter(kin_df.index, kin_df["PDOP"], s=size)
    axs[4].scatter(bad_pdop.index, bad_pdop["PDOP"], s=size * 2, color="red")
    axs[4].set_ylabel("log PDOP")
    axs[4].set_yscale("log")
    axs[4].set_ylim(1, 100)
    axs[5].scatter(kin_df.index, kin_df["wrms"], s=size)
    axs[5].set_ylabel("wrms mm")
    axs[0].ticklabel_format(axis="y", useOffset=False, style="plain")
    axs[1].ticklabel_format(axis="y", useOffset=False, style="plain")
    for ax in axs:
        ax.grid(True, c="lightgrey", zorder=0, lw=1, ls=":")
    plt.xticks(rotation=70)
    fig.suptitle(f"PRIDE-PPPAR results for {os.path.basename(title)}")
    fig.tight_layout()
    if save_as is not None:
        plt.savefig(save_as)


# ---------------------------------------------------------------------------
# KIN file reading
# ---------------------------------------------------------------------------


def kin_to_kin_position_df(source: str | Path) -> Union[pd.DataFrame, None]:
    """Create a KinPositionDataFrame from a kin file from PRIDE-PPP.

    This includes WRMS residuals.

    Parameters
    ----------
    source : str | Path
        The path to the kin file.

    Returns
    -------
    pd.DataFrame | None
        DataFrame with kinematic data and residuals, or None if the file
        cannot be parsed.
    """
    logger.info(f"Parsing KIN file: {source}")
    with open(source, "r") as file:
        lines = file.readlines()

    end_header_index = next(
        (i for i, line in enumerate(lines) if line.strip() == "END OF HEADER"), None
    )

    data = []
    if end_header_index is None:
        logger.error(f"GNSS: No header found in FILE {str(source)}")
        return None

    for idx, line in enumerate(lines[end_header_index + 2 :]):
        split_line = line.strip().split()
        selected_columns = split_line[:9] + [split_line[-1]]
        try:
            ppp: Union[PridePPP, ValidationError] = PridePPP.from_kin_file(
                selected_columns
            )
            data.append(ppp)
        except:
            pass

    if not data:
        logger.error(f"GNSS: No data found in FILE {source}")
        return None

    dataframe = pd.DataFrame([dict(pride_ppp) for pride_ppp in data])
    dataframe["time"] = dataframe["time"].dt.tz_localize("UTC")
    dataframe.set_index("time", inplace=True)
    logger.info(f"Parsed {len(dataframe)} records from KIN file {source}")

    # Add residuals data
    try:
        source_path = Path(source)
        res_pattern = source_path.stem.replace("kin_", "res_").replace(".kin", "")
        res_file = source_path.parent / f"{res_pattern}.res"

        if res_file.exists():
            logger.info(f"Adding residuals from {res_file}")
            wrms_df = get_wrms_from_res(res_file)

            if not wrms_df.empty:
                wrms_df.set_index("date", inplace=True)
                dataframe_sorted = dataframe.sort_index()
                wrms_sorted = wrms_df.sort_index()
                dataframe = pd.merge_asof(
                    dataframe_sorted,
                    wrms_sorted,
                    left_index=True,
                    right_index=True,
                    direction="nearest",
                    tolerance=pd.Timedelta(seconds=0.01),
                )
                logger.info(
                    f"Added WRMS residuals for {dataframe['wrms'].notna().sum()} of {len(dataframe)} records"
                )
            else:
                logger.warning(f"No WRMS data found in {res_file}")
                dataframe["wrms"] = None
        else:
            logger.warning(f"No corresponding RES file found for {source}")
            dataframe["wrms"] = None
    except Exception as e:
        logger.error(f"Error adding residuals: {e}")
        dataframe["wrms"] = None

    dataframe = dataframe.drop(
        columns=["modified_julian_date", "second_of_day"], errors="ignore"
    )
    dataframe.reset_index(inplace=True)
    logger.info(f"GNSS Parser: {dataframe.shape[0]} shots from FILE {str(source)}")
    return dataframe


def read_kin_data(kin_path):
    """Read a kin file and return a DataFrame.

    Parameters
    ----------
    kin_path : str
        The path to the kin file.

    Returns
    -------
    pd.DataFrame
        A DataFrame with the kin data.
    """
    with open(kin_path, "r") as kin_file:
        for i, line in enumerate(kin_file):
            if "END OF HEADER" in line:
                end_of_header = i + 1
                break

    cols = [
        "Mjd",
        "Sod",
        "*",
        "X",
        "Y",
        "Z",
        "Latitude",
        "Longitude",
        "Height",
        "Nsat",
        "G",
        "R",
        "E",
        "C2",
        "C3",
        "J",
        "PDOP",
    ]
    colspecs = [
        (0, 6),
        (6, 16),
        (16, 18),
        (18, 32),
        (32, 46),
        (46, 60),
        (60, 77),
        (77, 94),
        (94, 108),
        (108, 114),
        (114, 117),
        (117, 120),
        (120, 123),
        (123, 126),
        (126, 129),
        (129, 132),
        (132, 140),
    ]
    kin_df = pd.read_fwf(
        kin_path,
        header=end_of_header,
        colspecs=colspecs,
        names=cols,
        on_bad_lines="skip",
    )
    kin_df.set_index(
        pd.to_datetime(kin_df["Mjd"] + 2400000.5, unit="D", origin="julian")
        + pd.to_timedelta(kin_df["Sod"], unit="sec"),
        inplace=True,
    )
    return kin_df


def validate_kin_file(source: Union[str, Path]) -> bool:
    """Validate a kin file.

    This is done by checking if it can be parsed into a DataFrame and
    contains data.

    Parameters
    ----------
    source : str | Path
        The path to the kin file.

    Returns
    -------
    bool
        True if the kin file is valid, False otherwise.
    """
    if not isinstance(source, (str, Path)):
        logger.error(f"Invalid source type: {type(source)}")
        return False

    source = Path(source)
    if not source.exists():
        return False

    df = kin_to_kin_position_df(source)
    if df is None or df.empty:
        logger.error(f"Kin file {source} is invalid or contains no data")
        return False
    return True
