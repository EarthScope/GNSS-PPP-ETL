"""
RINEX utility functions.

Extract timestamps and time ranges from RINEX observation files,
and merge RINEX 2 broadcast ephemerides into RINEX 3 BRDM format.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import IO, Optional, Tuple

logger = logging.getLogger(__name__)


def _header_get_time(line: str) -> datetime:
    """Parse a timestamp from a RINEX header line containing ``GPS``.

    Expects the format produced by the ``TIME OF FIRST OBS`` /
    ``TIME OF LAST OBS`` header records::

        2025     1    15     0     0    0.0000000     GPS

    Everything before ``GPS`` is split on whitespace and interpreted as
    ``YYYY MM DD HH MI SS.sss``.

    Args:
        line: A single RINEX header line.

    Returns:
        Parsed UTC datetime (fractional seconds truncated to integer).
    """
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
    """Extract the epoch timestamp from a RINEX 2 observation record.

    Assumes a 2-digit year (added to 2000).  The line is whitespace-split
    and the first six tokens are interpreted as
    ``YY MM DD HH MI SS.sss``.

    Args:
        line: A single RINEX observation epoch line.

    Returns:
        Parsed UTC datetime.
    """
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

    if timestamp_data_start is not None and timestamp_data_end == timestamp_data_start:
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


# ---------------------------------------------------------------------------
# Broadcast navigation merge (RINEX 2 → RINEX 3 BRDM)
# ---------------------------------------------------------------------------


def _write_brdn(file: Path, prefix: str, fm: IO) -> None:
    """Write GPS broadcast ephemeris records from a RINEX 2 ``.n`` file.

    Args:
        file: Path to the RINEX 2 GPS broadcast file.
        prefix: Constellation prefix character (``'G'``).
        fm: Open file handle for the merged output.
    """
    try:
        with open(file) as fn:
            lines = fn.readlines()
    except Exception as e:
        logger.error("Unable to open or read file %s: %s", file, e)
        return

    in_header = True
    i = 1
    while i < len(lines):
        try:
            if not in_header:
                line = lines[i].replace("D", "e")
                prn = int(line[0:2])
                yyyy = int(line[3:5]) + 2000
                mm = int(line[6:8])
                dd = int(line[9:11])
                hh = int(line[12:14])
                mi = int(line[15:17])
                ss = round(float(line[18:22]))
                num2 = float(line[22:41])
                num3 = float(line[41:60])
                num4 = float(line[60:79])
                fm.write(
                    f"{prefix}{prn:02d} {yyyy:04d} {mm:02d} {dd:02d}"
                    f" {hh:02d} {mi:02d} {ss:02d}"
                    f" {num2:.12e} {num3:.12e} {num4:.12e}\n"
                )

                for t in range(1, 4):
                    line = lines[i + t].replace("D", "e")
                    num1 = float(line[3:22])
                    num2 = float(line[22:41])
                    num3 = float(line[41:60])
                    num4 = float(line[60:79])
                    fm.write(f"    {num1:.12e} {num2:.12e} {num3:.12e} {num4:.12e}\n")

                line = lines[i + 7].replace("D", "e")
                num1 = float(line[3:22])
                num2 = float(line[22:41])
                fm.write(f"    {num1:.12e} {num2:.12e}\n")
                i += 8
                if i >= len(lines):
                    break
            else:
                if "PGM / RUN BY / DATE" == lines[i][60:79]:
                    fm.write(lines[i])
                if "LEAP SECONDS" == lines[i][60:72]:
                    fm.write(lines[i])
                if "END OF HEADER" == lines[i][60:73]:
                    in_header = False
                    fm.write(lines[i])
                i += 1
        except Exception as e:
            logger.error("Error at line %d of file %s: %s", i, file, e)
            break


def _write_brdg(file: Path, prefix: str, fm: IO) -> None:
    """Write GLONASS broadcast ephemeris records from a RINEX 2 ``.g`` file.

    Args:
        file: Path to the RINEX 2 GLONASS broadcast file.
        prefix: Constellation prefix character (``'R'``).
        fm: Open file handle for the merged output.
    """
    try:
        with open(file) as fg:
            lines = fg.readlines()
    except Exception as e:
        logger.error("Unable to open or read file %s: %s", file, e)
        return

    in_header = True
    i = 1
    while i < len(lines):
        try:
            if not in_header:
                line = lines[i].replace("D", "e")
                prn = int(line[0:2])
                yyyy = int(line[3:5]) + 2000
                mm = int(line[6:8])
                dd = int(line[9:11])
                hh = int(line[12:14])
                mi = int(line[15:17])
                ss = round(float(line[18:22]))
                num2 = float(line[22:41])
                num3 = float(line[41:60])
                num4 = float(line[60:79])
                fm.write(
                    f"R{prn:02d} {yyyy:04d} {mm:02d} {dd:02d}"
                    f" {hh:02d} {mi:02d} {int(ss):02d}"
                    f"{num2: .12e}{num3: .12e}{num4: .12e}\n"
                )
                for t in range(1, 4):
                    line = lines[i + t].replace("D", "e")
                    num1 = float(line[3:22])
                    num2 = float(line[22:41])
                    num3 = float(line[41:60])
                    num4 = float(line[60:79])
                    fm.write(f"    {num1: .12e}{num2: .12e}{num3: .12e}{num4: .12e}\n")
                i += 4
                if i >= len(lines):
                    break
            else:
                if "END OF HEADER" == lines[i][60:73]:
                    in_header = False
                i += 1
        except Exception as e:
            logger.error("Error at line %d of file %s: %s", i, file, e)
            break


def merge_broadcast_files(
    brdn: Path,
    brdg: Path,
    output_folder: Path,
) -> Optional[Path]:
    """Merge GPS and GLONASS RINEX 2 broadcast files into a RINEX 3 BRDM file.

    Inspired by ``PrideLab/PRIDE-PPPAR/scripts/merge2brdm.py``.

    Args:
        brdn: Path to the GPS broadcast ephemeris (``.n``) file.
        brdg: Path to the GLONASS broadcast ephemeris (``.g``) file.
        output_folder: Directory where the merged BRDM file will be written.

    Returns:
        Path to the merged BRDM file, or ``None`` on failure.
    """
    logger.info("Merging %s and %s into a single BRDM file.", brdn, brdg)

    ddd = brdn.name[4:7]
    yy = brdn.name[9:11]
    if brdg.name[4:7] != ddd or brdg.name[9:11] != yy:
        logger.error(
            "Inconsistent file names: %s vs %s (DOY or year mismatch)", brdn, brdg
        )
        return None

    brdm = output_folder / f"brdm{ddd}0.{yy}p"
    with open(brdm, "w") as fm:
        fm.write(
            "     3.04           NAVIGATION DATA     "
            "M (Mixed)           RINEX VERSION / TYPE\n"
        )
        _write_brdn(brdn, "G", fm)
        _write_brdg(brdg, "R", fm)

    if brdm.exists():
        logger.info("Files merged into %s", brdm)
        return brdm
    return None
