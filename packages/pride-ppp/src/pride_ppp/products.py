"""
GNSS product download and management operations.

Handles FTP-based retrieval of orbit, clock, bias, ERP, and navigation
products from multiple IGS data centres.
"""

import datetime
import gzip
import re
import tempfile
from ftplib import FTP
from pathlib import Path
from typing import IO, Dict, Literal, Optional

import logging

from .schemas import CLSIGS, GSSC, RemoteQuery, RemoteResourceFTP, WuhanIGS
from .config import PRIDEPPPFileConfig, SatelliteProducts
from .rinex import rinex_get_time_range

logger = logging.getLogger(__name__)


def update_source(source: RemoteResourceFTP) -> RemoteResourceFTP:
    """
    Get the contents of the directory on a remote FTP server and return the
    first file that matches the sorted remote query.

    Parameters
    ----------
    source : RemoteResourceFTP
        An object containing the FTP server details, directory to list,
        and the remote query for matching files.

    Returns
    -------
    RemoteResourceFTP
        The updated source object with the ``file_name`` attribute set.
    """
    assert isinstance(
        source.remote_query, RemoteQuery
    ), f"Remote query not set for {source}"

    try:
        with FTP(source.ftpserver.replace("ftp://", ""), timeout=60) as ftp:
            ftp.set_pasv(True)
            ftp.login()
            ftp.cwd("/" + source.directory)
            dir_list = ftp.nlst()
    except Exception as e:
        logger.error(
            f"Failed to list directory {source.directory} on {source.ftpserver} | {e}"
        )
        return source

    remote_query = source.remote_query

    dir_match = [d for d in dir_list if remote_query.pattern.search(d)]
    if len(dir_match) == 0:
        logger.error(f"No match found for {remote_query.pattern}")
        return source

    sorted_match = []
    if remote_query.sort_order is not None:
        for prod_type in remote_query.sort_order:
            for idx, d in enumerate(dir_match):
                if prod_type in d:
                    sorted_match.append(dir_match.pop(idx))
    sorted_match.extend(dir_match)
    source.file_name = sorted_match[0]
    logger.info(f"Match found for {remote_query.pattern} : {source.file_name}")
    return source


def download(source: RemoteResourceFTP, dest: Path) -> Path:
    """
    Download a file from a remote FTP server to a local destination.

    Parameters
    ----------
    source : RemoteResourceFTP
        An object containing the FTP server details, directory, and file name.
    dest : Path
        The local path where the file will be saved.

    Returns
    -------
    Path
        The local path where the file has been saved.
    """
    logger.info(f"\nAttempting Download of {str(source)} to {str(dest)}\n")
    with FTP(source.ftpserver.replace("ftp://", ""), timeout=60) as ftp:
        ftp.set_pasv(True)
        ftp.login()
        ftp.cwd("/" + source.directory)
        with open(dest, "wb") as f:
            ftp.retrbinary(f"RETR {source.file_name}", f.write)
    logger.info(f"\nDownloaded {str(source)} to {str(dest)}\n")
    return dest


def uncompress_file(file_path: Path, dest_dir: Optional[Path] = None) -> Optional[Path]:
    """
    Decompress a gzip file and return the path of the decompressed file.

    Parameters
    ----------
    file_path : Path
        The path of the compressed file.
    dest_dir : Path, optional
        Destination directory for the decompressed file.

    Returns
    -------
    Path or None
        The path of the decompressed file, or None on failure.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File {file_path} does not exist.")

    out_file_path = file_path.with_suffix("")
    if dest_dir is not None:
        out_file_path = dest_dir / out_file_path.name
        if not dest_dir.exists():
            dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        with gzip.open(file_path, "rb") as f_in:
            with open(out_file_path, "wb") as f_out:
                f_out.write(f_in.read())
    except EOFError as e:
        logger.error(f"Failed to decompress {file_path}: {e}")
        file_path.unlink(missing_ok=True)
        return None
    file_path.unlink(missing_ok=True)
    return out_file_path


def get_daily_rinex_url(date: datetime.date) -> Dict[str, Dict[str, RemoteResourceFTP]]:
    """
    Return ``RemoteResourceFTP`` objects for IGS RINEX observation files
    for a given date.

    Parameters
    ----------
    date : datetime.date
        The date for which the RINEX observation file is required.

    Returns
    -------
    dict
        A dictionary containing URLs for RINEX 2 and RINEX 3 observation files.
    """
    urls = {
        "rinex_2": {
            "wuhan": {
                "glonass": WuhanIGS.get_rinex_2_nav(date, constellation="glonass"),
                "gps": WuhanIGS.get_rinex_2_nav(date, constellation="gps"),
            },
            "gssc": {
                "glonass": GSSC.get_rinex_2_nav(date, constellation="glonass"),
                "gps": GSSC.get_rinex_2_nav(date, constellation="gps"),
            },
        },
        "rinex_3": {
            "igs_gnss": CLSIGS.get_rinex_3_nav(date),
            "wuhan_gps": WuhanIGS.get_rinex_3_nav(date),
            "gssc_gnss": GSSC.get_rinex_3_nav(date),
        },
    }
    return urls


def get_gnss_common_products_urls(date: datetime.date) -> Dict[str, Dict[str, RemoteResourceFTP]]:
    """
    Retrieve GNSS common product ``RemoteResourceFTP`` objects for a given date.

    Returns FTP resources for SP3, CLK, bias, OBX, and ERP products
    from WuhanIGS and CLSIGS.
    """
    urls = {
        "sp3": {
            "cligs": CLSIGS.get_product_sp3(date),
            "wuhan": WuhanIGS.get_product_sp3(date),
        },
        "clk": {
            "cligs": CLSIGS.get_product_clk(date),
            "wuhan": WuhanIGS.get_product_clk(date),
        },
        "bias": {
            "cligs": CLSIGS.get_product_bias(date),
            "wuhan": WuhanIGS.get_product_bias(date),
        },
        "obx": {
            "cligs": CLSIGS.get_product_obx(date),
            "wuhan": WuhanIGS.get_product_obx(date),
        },
        "erp": {
            "cligs": CLSIGS.get_product_erp(date),
            "wuhan": WuhanIGS.get_product_erp(date),
        },
    }
    return urls


def merge_broadcast_files(brdn: Path, brdg: Path, output_folder: Path) -> Optional[Path]:
    """
    Merge GPS and GLONASS broadcast ephemerides into a single BRDM file.

    Inspired by https://github.com/PrideLab/PRIDE-PPPAR/blob/master/scripts/merge2brdm.py

    Parameters
    ----------
    brdn : Path
        Path to the GPS broadcast ephemerides file.
    brdg : Path
        Path to the GLONASS broadcast ephemerides file.
    output_folder : Path
        Path to the output folder where the merged file will be saved.

    Returns
    -------
    Path or None
        Path to the merged BRDM file.
    """
    logger.info(f"Merging {brdn} and {brdg} into a single BRDM file.")

    def write_brdn(file: Path, prefix: str, fm: IO):
        try:
            fn = open(file)
            lines = fn.readlines()
            in_header = True
        except Exception as e:
            print(f"***ERROR: unable to open or read file {file}: {e}")
            return

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
                    num2 = eval(line[22:41])
                    num3 = eval(line[41:60])
                    num4 = eval(line[60:79])
                    logger.debug(
                        f"{prefix}{prn:02d} {yyyy:04d} {mm:02d} {dd:02d} {hh:02d} {mi:02d} {ss:02d} {num2:.12e} {num3:.12e} {num4:.12e}\n"
                    )
                    fm.write(
                        f"{prefix}{prn:02d} {yyyy:04d} {mm:02d} {dd:02d} {hh:02d} {mi:02d} {ss:02d} {num2:.12e} {num3:.12e} {num4:.12e}\n"
                    )
                    for t in range(1, 4):
                        line = lines[i + t].replace("D", "e")
                        num1 = eval(line[3:22])
                        num2 = eval(line[22:41])
                        num3 = eval(line[41:60])
                        num4 = eval(line[60:79])
                        logger.debug(f"{t}    {num1} {num2} {num3} {num4}\n")
                        logger.debug(
                            f"    {num1:.12e} {num2:.12e} {num3:.12e} {num4:.12e}\n"
                        )
                        fm.write(
                            f"    {num1:.12e} {num2:.12e} {num3:.12e} {num4:.12e}\n"
                        )

                    line = lines[i + 7].replace("D", "e")
                    num1 = eval(line[3:22])
                    num2 = eval(line[22:41])
                    fm.write(f"    {num1:.12e} {num2:.12e}\n")
                    i += 8
                    if i >= len(lines):
                        break
                else:
                    if "PGM / RUN BY / DATE" == lines[i][60:79]:
                        fm.write(lines[i])
                    if "LEAP SECONDS" == lines[i][60:72]:
                        leap_n = int(lines[i][1:6])
                        fm.write(lines[i])
                    if "END OF HEADER" == lines[i][60:73]:
                        in_header = False
                        fm.write(lines[i])
                    i = i + 1
            except Exception as e:
                logger.error(
                    f"***ERROR: unexpected ERROR occurred at line {i} of file {file}: {e}"
                )
                break
        fn.close()

    def write_brdg(file: Path, prefix: str, fm: IO):
        try:
            fg = open(file)
            lines = fg.readlines()
            in_header = True
        except Exception as e:
            logger.error(f"***ERROR: unable to open or read file {file}: {e}")
            return

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
                    num2 = eval(line[22:41])
                    num3 = eval(line[41:60])
                    num4 = eval(line[60:79])
                    fm.write(
                        "R{:02d} {:04d} {:02d} {:02d} {:02d} {:02d} {:02d}{: .12e}{: .12e}{: .12e}\n".format(
                            prn, yyyy, mm, dd, hh, mi, int(ss), num2, num3, num4
                        )
                    )
                    for t in range(1, 4):
                        line = lines[i + t].replace("D", "e")
                        num1 = eval(line[3:22])
                        num2 = eval(line[22:41])
                        num3 = eval(line[41:60])
                        num4 = eval(line[60:79])
                        fm.write(
                            "    {: .12e}{: .12e}{: .12e}{: .12e}\n".format(
                                num1, num2, num3, num4
                            )
                        )
                    i = i + 4
                    if i >= len(lines):
                        break
                else:
                    if "LEAP SECONDS" == lines[i][60:72]:
                        leap_g = int(lines[i][1:6])
                    if "END OF HEADER" == lines[i][60:73]:
                        in_header = False
                    i = i + 1
            except Exception as e:
                logger.error(
                    f"***ERROR: unexpected ERROR occurred at line {i} of file {file}: {e}"
                )
                logger.debug(lines[i])
                break
        fg.close()

    DDD = brdn.name[4:7]
    YY = brdn.name[9:11]
    if brdg.name[4:7] != DDD or brdg.name[9:11] != YY:
        print("***ERROR: inconsistent file name:")
        print(f"  {brdn} {brdg}")
        return

    brdm = output_folder / f"brdm{DDD}0.{YY}p"
    fm = open(brdm, "w")
    fm.write(
        "     3.04           NAVIGATION DATA     M (Mixed)           RINEX VERSION / TYPE\n"
    )
    write_brdn(brdn, "G", fm)
    write_brdg(brdg, "R", fm)
    fm.close()

    if brdm.exists():
        logger.info(f"Files merged into {str(brdm)}")
        return brdm
    logger.error(f"Failed to merge files into {str(brdm)}")
    return None


def get_nav_file(rinex_path: Path, override: bool = False) -> Optional[Path]:
    """
    Build a navigation file for a given RINEX file by downloading
    the necessary files from IGS FTP servers.

    Parameters
    ----------
    rinex_path : Path
        The path to the RINEX file.
    override : bool
        If True, re-download even if a nav file already exists.

    Returns
    -------
    Path or None
        The path to the navigation file.
    """
    response = f"\nAttempting to build nav file for {str(rinex_path)}"
    logger.debug(response)

    start_date = None
    with open(rinex_path) as f:
        files = f.readlines()
        for line in files:
            if "TIME OF FIRST OBS" in line:
                time_values = line.split("GPS")[0].strip().split()
                start_date = datetime.date(
                    year=int(time_values[0]),
                    month=int(time_values[1]),
                    day=int(time_values[2]),
                )
                break

    if start_date is None:
        logger.error("No TIME OF FIRST OBS found in RINEX file.")
        return

    year = str(start_date.year)
    doy = str(start_date.timetuple().tm_yday)
    brdc_pattern = re.compile(rf"BRDC.*{year}{doy}.*rnx.*")
    brdm_pattern = re.compile(rf"brdm{doy}0.{year[-2:]}p")

    found_nav_files = [
        x
        for x in rinex_path.parent.glob("*")
        if brdc_pattern.search(x.name) or brdm_pattern.search(x.name)
    ]

    for nav_file in found_nav_files:
        if nav_file.stat().st_size > 0 and not override:
            logger.debug(f"{nav_file} already exists.")
            return nav_file

    remote_resource_dict: Dict[str, RemoteResourceFTP] = get_daily_rinex_url(start_date)
    for source, remote_resource in remote_resource_dict["rinex_3"].items():
        remote_resource_updated = update_source(remote_resource)
        if remote_resource_updated.file_name is None:
            continue

        logger.debug(f"Attempting to download {source} - {str(remote_resource)}")

        local_path = rinex_path.parent / remote_resource.file_name
        try:
            download(remote_resource, local_path)
        except Exception as e:
            logger.error(f"Failed to download {str(remote_resource)} | {e}")
            continue

        if local_path.exists():
            logger.debug(
                f"Successfully downloaded {str(remote_resource)} to {str(local_path)}"
            )
            return local_path

    with tempfile.TemporaryDirectory() as tempdir:
        for source, constellations in remote_resource_dict["rinex_2"].items():
            gps_url: RemoteResourceFTP = constellations["gps"]
            glonass_url: RemoteResourceFTP = constellations["glonass"]

            gps_url_updated = update_source(gps_url)
            glonass_url_updated = update_source(glonass_url)
            if (
                gps_url_updated.file_name is None
                or glonass_url_updated.file_name is None
            ):
                continue

            gps_local_name = gps_url.file_name
            glonass_local_name = glonass_url.file_name
            gps_dl_path = Path(tempdir) / gps_local_name
            glonass_dl_path = Path(tempdir) / glonass_local_name

            logger.debug(f"Attempting to download {source} From {str(gps_url)}")

            try:
                download(gps_url, gps_dl_path)
                download(glonass_url, glonass_dl_path)
            except Exception as e:
                logger.error(
                    f"Failed to download {str(gps_url)} To {str(gps_dl_path.name)} "
                    f"or {str(glonass_url)} To {str(glonass_dl_path.name)} | {e}"
                )
                continue

            if gps_dl_path.exists() and glonass_dl_path.exists():
                gps_dl_path = uncompress_file(gps_dl_path)
                glonass_dl_path = uncompress_file(glonass_dl_path)
                if (
                    brdm_path := merge_broadcast_files(
                        gps_dl_path, glonass_dl_path, rinex_path.parent
                    )
                ) is not None:
                    logger.debug(f"Successfully built {brdm_path}")
                    return brdm_path
            else:
                logger.error(f"Failed to download {str(gps_url)} or {str(glonass_url)}")

    logger.error("Failed to build or locate navigation file")


def get_gnss_products(
    rinex_path: Path,
    pride_dir: Path,
    override: bool = False,
    source: Literal["all", "wuhan", "cligs"] = "all",
    date: Optional[datetime.date | datetime.datetime] = None,
    override_config: bool = True,
) -> Optional[Path]:
    """
    Generate or retrieve GNSS products for a given RINEX file or date.

    Returns a PRIDE config file path that catalogs the products.

    Parameters
    ----------
    rinex_path : Path
        The path to the RINEX file.
    pride_dir : Path
        The directory where the PRIDE products are stored.
    override : bool
        If True, re-download products even if they already exist.
    source : str
        The source from which to download (``"all"``, ``"wuhan"``, or ``"cligs"``).
    date : datetime.date or datetime.datetime, optional
        The date for which to retrieve products.
    override_config : bool
        If True, re-download products even if a config file already exists.

    Returns
    -------
    Path or None
        The path to the config file, or None on failure.
    """
    assert source in ["all", "wuhan", "cligs"], f"Invalid source {source}"
    config_template = None
    start_date = None

    if rinex_path is not None:
        start_date, _ = rinex_get_time_range(rinex_path)
        if start_date is None:
            logger.error("No TIME OF FIRST OBS found in RINEX file.")
            return
    elif date is not None:
        if isinstance(date, datetime.datetime):
            start_date = date.date()
        elif isinstance(date, datetime.date):
            start_date = date
        else:
            raise TypeError(
                f"Invalid date type {type(date)}. Must be datetime.date or datetime.datetime"
            )
    else:
        raise ValueError("Either rinex_path or date must be provided")

    year = str(start_date.year)
    doy = str(start_date.timetuple().tm_yday)

    common_product_dir = pride_dir / year / "product" / "common"
    common_product_dir.mkdir(exist_ok=True, parents=True)

    config_template_file_path = pride_dir / year / doy / "config_file"
    if config_template_file_path.exists():
        try:
            config_template = PRIDEPPPFileConfig.read_config_file(
                config_template_file_path
            )
            product_directory = Path(
                config_template.satellite_products.product_directory
            )
            assert (
                product_directory.exists()
            ), f"Product directory {product_directory} does not exist"
            for (
                name,
                product,
            ) in config_template.satellite_products.model_dump().items():
                if name != "product_directory" and name != "leo_quaternions":
                    test_path = product_directory / "common" / product
                    if not test_path.exists():
                        logger.error(f"Product {name} not found in {test_path}")
                        raise FileNotFoundError(
                            f"Product {name} not found in {test_path}"
                        )
        except Exception as e:
            config_template = None
            logger.error(
                f"Failed to load config file {config_template_file_path}: {e}"
            )

    if config_template is not None and not override_config:
        return config_template_file_path

    cp_dir_list = list(common_product_dir.glob("*"))
    remote_resource_dict: Dict[str, Dict[str, RemoteResourceFTP]] = (
        get_gnss_common_products_urls(start_date)
    )

    product_status = {}

    for product_type, sources in remote_resource_dict.items():
        logger.debug(f"Attempting to download {product_type} products")
        if product_type not in product_status:
            product_status[product_type] = "False"

        for dl_source, remote_resource in sources.items():
            if source != "all" and dl_source != source:
                continue
            found_files = [
                f
                for f in cp_dir_list
                if remote_resource.remote_query.pattern.match(f.name)
            ]
            if remote_resource.remote_query.sort_order is not None:
                for prod_type in remote_resource.remote_query.sort_order[::-1]:
                    for idx, f in enumerate(found_files):
                        if prod_type in f.name:
                            found_files.insert(0, found_files.pop(idx))

            if found_files and not override:
                logger.debug(f"Found {found_files[0]} for product {product_type}")
                to_decompress = found_files[0]
                if to_decompress.suffix == ".gz":
                    decompressed_file = uncompress_file(
                        to_decompress, common_product_dir
                    )
                    if decompressed_file is None:
                        logger.error(
                            f"Failed to decompress {to_decompress} for product {product_type}"
                        )
                        continue
                else:
                    decompressed_file = to_decompress
                logger.debug(
                    f"Using existing file {decompressed_file} for product {product_type}"
                )
                product_status[product_type] = str(decompressed_file.name)
                break

            remote_resource_updated = update_source(remote_resource)
            if remote_resource_updated.file_name is None:
                continue

            local_path = common_product_dir / remote_resource.file_name
            try:
                logger.debug(
                    f"Attempting to download {product_type} product from {str(remote_resource)}"
                )
                download(remote_resource, local_path)
                logger.debug(
                    f"\nSuccessfully downloaded {product_type} FROM {str(remote_resource)} TO {str(local_path)}\n"
                )
                if local_path.suffix == ".gz":
                    local_path = uncompress_file(local_path, common_product_dir)
                    logger.debug(f"Uncompressed {str(local_path)}")
                product_status[product_type] = str(local_path.name)
                break
            except Exception as e:
                logger.error(f"Failed to download {str(remote_resource)} | {e}")
                if local_path.exists() and local_path.stat().st_size == 0:
                    local_path.unlink()
                continue

    for product_type, product_path in product_status.items():
        logger.debug(f"{product_type} : {product_path}")

    satellite_products = SatelliteProducts(
        satellite_orbit=product_status.get("sp3", None),
        satellite_clock=product_status.get("clk", None),
        code_phase_bias=product_status.get("bias", None),
        quaternions=product_status.get("obx", None),
        erp=product_status.get("erp", None),
        product_directory=str(common_product_dir.parent),
    )
    config_template = PRIDEPPPFileConfig.load_default()
    config_template.satellite_products = satellite_products
    config_template_file_path = pride_dir / year / doy / "config_file"
    config_template.write_config_file(config_template_file_path)
    return config_template_file_path
