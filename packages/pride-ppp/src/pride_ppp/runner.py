"""
PRIDE-PPP-AR subprocess runner.

Wraps the ``pdp3`` binary to generate kinematic (``.kin``) and residual
(``.res``) files from RINEX observations.
"""

import datetime
import logging
import shutil
import subprocess
from collections import namedtuple
from pathlib import Path
from typing import Tuple

from .cli import PrideCLIConfig
from .output import validate_kin_file
from .rinex import rinex_get_time_range

logger = logging.getLogger(__name__)

# Make output of subprocess.Popen identical to subprocess.run
_Result = namedtuple("_Result", ["stdout", "stderr"])


def _parse_cli_logs(result, log: logging.Logger) -> None:
    """Log stdout/stderr from a subprocess result."""
    if result.stdout:
        for line in result.stdout.strip().splitlines():
            log.info(line)
    if result.stderr:
        for line in result.stderr.strip().splitlines():
            log.warning(line)


def rinex_to_kin(
    source: str,
    writedir: Path,
    pridedir: Path,
    site="SIT1",
    pride_cli_config: PrideCLIConfig = None,
) -> Tuple[Path, Path]:
    """Generate kinematic and residual files from a RINEX file.

    This function is a wrapper for the PRIDE-PPP processing tool (pdp3).

    Parameters
    ----------
    source : str
        The source RINEX file to convert.
    writedir : Path
        The directory to write the converted kin file.
    pridedir : Path
        The directory where PRIDE-PPP observables are stored.
    site : str, optional
        The site name, by default ``"SIT1"``.
    pride_cli_config : PrideCLIConfig, optional
        The configuration for PRIDE-PPP processing. If None, uses default
        settings.

    Returns
    -------
    Tuple[Path, Path]
        The generated kin and result files as Path objects.

    Raises
    ------
    FileNotFoundError
        If the PRIDE-PPP binary is not found in the system path.
    FileNotFoundError
        If the source RINEX file does not exist.
    """
    # Check if the pride binary is in the path
    if not shutil.which("pdp3"):
        raise FileNotFoundError("PRIDE-PPP binary 'pdp3' not found in path")

    if isinstance(source, str):
        source = Path(source)

    if not source.exists():
        logger.error(f"RINEX file {source} not found")
        raise FileNotFoundError(f"RINEX file {source} not found")

    if pride_cli_config is None:
        pride_cli_config = PrideCLIConfig()

    # Step 1: Determine the year and day of year from the RINEX file
    timestamps: Tuple[datetime.datetime, datetime.datetime] = rinex_get_time_range(
        source
    )

    year, doy = (
        timestamps[0].year,
        timestamps[0].timetuple().tm_yday,
    )
    file_dir = Path(pridedir) / str(year) / str(doy)

    kin_file_path = file_dir / f"kin_{str(year)}{str(doy)}_{site.lower()}"
    res_file_path = file_dir / f"res_{str(year)}{str(doy)}_{site.lower()}"
    kin_file_new = writedir / (kin_file_path.name + ".kin")
    res_file_new = writedir / (res_file_path.name + ".res")
    kin_file = None
    res_file = None

    # Step 2: Determine if processing is needed
    logger.info(f"Determining if processing is needed for RINEX file {source}")

    # Case 1: kin file already in writedir
    if validate_kin_file(kin_file_new) and not pride_cli_config.override:
        logger.info(f"Kin file {kin_file_new} already exists, skipping processing")
        kin_file = kin_file_new
        if res_file_new.exists():
            logger.info(f"Res file {res_file_new} already exists, skipping processing")
            res_file = res_file_new
        else:
            logger.warning(f"Res file {res_file_new} not found")
        return kin_file, res_file

    # Case 2: kin file in pridedir but not writedir
    if validate_kin_file(kin_file_path) and not pride_cli_config.override:
        shutil.move(src=kin_file_path, dst=kin_file_new)
        kin_file = kin_file_new
        logger.info(f"Kin file {kin_file} already exists, moved to {kin_file_new}")
        if res_file_path.exists():
            shutil.move(src=res_file_path, dst=res_file_new)
            res_file = res_file_new
            logger.info(f"Res file {res_file} already exists, moved to {res_file_new}")
        else:
            logger.warning(f"Res file {res_file_path} not found")
        return kin_file, res_file

    # Case 3: run pdp3
    pdp_command = pride_cli_config.generate_pdp_command(
        site=site,
        local_file_path=source,
    )

    logger.info(f"Running pdp3 with command: {' '.join(pdp_command)}")
    process = subprocess.Popen(
        " ".join(pdp_command),
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(pridedir),
        text=True,
    )

    stdout, stderr = process.communicate()
    _results = _Result(stdout=stdout, stderr=stderr)
    _parse_cli_logs(result=_results, log=logger)

    if kin_file_path.exists():
        kin_file_new = writedir / (kin_file_path.name + ".kin")
        shutil.move(src=kin_file_path, dst=kin_file_new)
        kin_file = kin_file_new
        logger.info(f"Generated kin file {kin_file} from RINEX file {source}")
    else:
        logger.error(f"No kin file generated from RINEX {source}")
        return None, None

    if res_file_path.exists():
        res_file_new = writedir / (res_file_path.name + ".res")
        shutil.move(src=res_file_path, dst=res_file_new)
        res_file = res_file_new
        logger.info(f"Found PRIDE res file {res_file}")
    else:
        logger.error(f"No res file generated from RINEX {source}")
        return kin_file, None

    return kin_file, res_file
