"""
RINEX utility functions.

Extract timestamps and time ranges from RINEX observation files.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Tuple

logger = logging.getLogger(__name__)


def _header_get_time(line: str) -> datetime:
    time_values = line.split("GPS")[0].strip().split()
    return datetime(
        year=int(time_values[0]),
        month=int(time_values[1]),
        day=int(time_values[2]),
        hour=int(time_values[3]),
        minute=int(time_values[4]),
        second=int(float(time_values[5])),
    )


def epoch_get_time(line: str) -> datetime:
    """Extract the epoch time from a RINEX observation line."""
    date_line = line.strip().split()
    return datetime(
        year=2000 + int(date_line[0]),
        month=int(date_line[1]),
        day=int(date_line[2]),
        hour=int(date_line[3]),
        minute=int(date_line[4]),
        second=int(float(date_line[5])),
    )


def rinex_get_time_range(source: str | Path) -> Tuple[datetime, datetime]:
    """
    Extract the time range from a RINEX observation file.

    Parameters
    ----------
    source : str | Path
        Path to the RINEX observation file.

    Returns
    -------
    Tuple[datetime, datetime]
        Start and end timestamps.

    Raises
    ------
    ValueError
        If the time range cannot be extracted.
    """
    timestamp_data_start = None
    timestamp_data_end = None

    with open(source) as f:
        files = f.readlines()

        for line in files:
            if timestamp_data_start is None:
                if "TIME OF FIRST OBS" in line:
                    start_time = _header_get_time(line)
                    timestamp_data_start = start_time
                    timestamp_data_end = start_time
                    year = str(timestamp_data_start.year)[2:]
                    break

            if timestamp_data_start is not None:
                if line.strip().startswith(year):
                    try:
                        current_date = epoch_get_time(line)
                        if current_date and current_date > timestamp_data_start:
                            timestamp_data_end = current_date
                    except Exception:
                        pass

    if (
        timestamp_data_start is not None
        and timestamp_data_end == timestamp_data_start
    ):
        timestamp_data_end = datetime(
            year=timestamp_data_start.year,
            month=timestamp_data_start.month,
            day=timestamp_data_start.day,
            hour=23,
            minute=59,
            second=59,
            microsecond=999999,
        )

    if timestamp_data_start is None or timestamp_data_end is None:
        logger.error("Failed to extract time range from %s", source)
        raise ValueError(f"Failed to extract time range from {source}")

    return timestamp_data_start, timestamp_data_end
