"""
FTP download utilities for GNSS precise products.

All functions are pure (no Dagster coupling) so they can be unit-tested
independently against live or mock FTP servers.

Source/quality priority strategy
---------------------------------
* **Server**  — Wuhan IGS first, CLIGS as fallback (configurable via
  ``SERVER_PRIORITY``).
* **Quality** — FINAL (FIN) → RAPID (RAP) → REAL_TIME_STREAMING (RTS).
  The FTP directory is listed *once* per server visit; all three quality-level
  regex patterns are tested against that cached listing to avoid repeated
  connections.
"""
from __future__ import annotations

import gzip
import io
import re
from ftplib import FTP, all_errors as FTP_ERRORS
from pathlib import Path
from typing import Optional

from .product_sources import (
    ProductQuality,
    ProductSourceCollectionFTP,
    ProductSourcePathFTP,
    ProductSourcesFTP,
)

# Default server preference: Wuhan primary, CLIGS secondary.
SERVER_PRIORITY: list[str] = ["wuhan", "cligs"]

# Quality fallback order.
QUALITY_PRIORITY: list[ProductQuality] = [
    ProductQuality.FINAL,
    ProductQuality.RAPID,
    ProductQuality.REAL_TIME_STREAMING,
]

# Maps ProductQuality → field name on ProductSourceCollectionFTP
_QUALITY_ATTR: dict[ProductQuality, str] = {
    ProductQuality.FINAL: "final",
    ProductQuality.RAPID: "rapid",
    ProductQuality.REAL_TIME_STREAMING: "rts",
}


# ---------------------------------------------------------------------------
# Low-level FTP helpers
# ---------------------------------------------------------------------------


def ftp_list_directory(
    ftpserver: str,
    directory: str,
    timeout: int = 60,
) -> list[str]:
    """
    Connect to *ftpserver*, change to *directory*, and return the file listing.

    Returns an empty list on any connection or command error so the caller
    can decide how to handle the failure.
    """
    clean = ftpserver.replace("ftp://", "")
    try:
        with FTP(clean, timeout=timeout) as ftp:
            ftp.set_pasv(True)
            ftp.login()
            ftp.cwd("/" + directory)
            return ftp.nlst()
    except Exception:  # noqa: BLE001
        return []


def ftp_download_file(
    ftpserver: str,
    directory: str,
    filename: str,
    dest_path: Path,
    timeout: int = 180,
) -> bool:
    """
    Download *filename* from *ftpserver*/*directory* to *dest_path*.

    Parent directories are created automatically.  Returns *True* on success
    (file exists and is non-empty), *False* on any failure (partial download
    is deleted before returning).
    """
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    clean = ftpserver.replace("ftp://", "")
    try:
        with FTP(clean, timeout=timeout) as ftp:
            ftp.set_pasv(True)
            ftp.login()
            ftp.cwd("/" + directory)
            with open(dest_path, "wb") as fh:
                ftp.retrbinary(f"RETR {filename}", fh.write)
        if dest_path.exists() and dest_path.stat().st_size > 0:
            return True
        dest_path.unlink(missing_ok=True)
        return False
    except Exception:  # noqa: BLE001
        dest_path.unlink(missing_ok=True)
        return False


def ftp_try_download_md5_sidecar(
    ftpserver: str,
    directory: str,
    filename: str,
    dest_dir: Path,
) -> Optional[Path]:
    """
    Attempt to download a ``<filename>.md5`` sidecar from the same FTP
    location.  Returns the local path if downloaded, or *None* if absent or
    download fails (non-blocking — callers should not depend on this).
    """
    md5_filename = filename + ".md5"
    md5_dest = dest_dir / md5_filename
    success = ftp_download_file(ftpserver, directory, md5_filename, md5_dest, timeout=30)
    return md5_dest if success else None


# ---------------------------------------------------------------------------
# Match helpers
# ---------------------------------------------------------------------------


def find_best_match_in_listing(
    dir_listing: list[str],
    file_regex: str,
) -> Optional[str]:
    """
    Search *dir_listing* with *file_regex* and return the first match, or
    *None* if nothing matches.
    """
    pattern = re.compile(file_regex)
    for entry in dir_listing:
        if pattern.search(entry):
            return entry
    return None


# ---------------------------------------------------------------------------
# Product resolution (single server, all quality levels)
# ---------------------------------------------------------------------------


def resolve_product_source(
    source_collection: ProductSourceCollectionFTP,
) -> Optional[tuple[str, str, str, str]]:
    """
    List the FTP directory *once* then test FINAL → RAPID → RTS regex patterns
    against that listing.

    All quality levels in a ``ProductSourceCollectionFTP`` share the same
    FTP server and directory path; only the filename regex differs.

    Returns
    -------
    tuple[ftpserver, directory, filename, quality_label] or *None*
    """
    ftpserver = source_collection.final.ftpserver
    directory = source_collection.final.directory

    dir_listing = ftp_list_directory(ftpserver, directory)
    if not dir_listing:
        return None

    for quality in QUALITY_PRIORITY:
        source_path: ProductSourcePathFTP = getattr(
            source_collection, _QUALITY_ATTR[quality]
        )
        filename = find_best_match_in_listing(dir_listing, source_path.file_regex)
        if filename:
            return (ftpserver, directory, filename, quality.value)

    return None


# ---------------------------------------------------------------------------
# Main downloader — multi-server, multi-quality fallback
# ---------------------------------------------------------------------------


def download_product_with_fallback(
    source_map: dict[str, ProductSourcesFTP],
    product_attr: str,
    dest_dir: Path,
    server_priority: list[str] = SERVER_PRIORITY,
) -> Optional[tuple[Path, str, str]]:
    """
    Download a GNSS product file trying servers and quality levels in priority
    order.

    Parameters
    ----------
    source_map:
        Mapping of server name → ``ProductSourcesFTP`` (the output of
        ``load_product_sources_FTP``).
    product_attr:
        Attribute name on ``ProductSourcesFTP``, e.g. ``"sp3"``, ``"clk"``,
        ``"bias"``.
    dest_dir:
        Local directory to save the file.
    server_priority:
        Ordered list of server names to try; defaults to
        ``["wuhan", "cligs"]``.

    Returns
    -------
    (local_path, server_name, quality_label) on success, or *None* if every
    server and quality level was exhausted.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)

    for server_name in server_priority:
        if server_name not in source_map:
            continue

        product_sources: ProductSourcesFTP = source_map[server_name]

        # Some product types may not be present for all sources
        if not hasattr(product_sources, product_attr):
            continue
        source_collection: ProductSourceCollectionFTP = getattr(
            product_sources, product_attr
        )
        if source_collection is None:
            continue

        resolved = resolve_product_source(source_collection)
        if resolved is None:
            continue

        ftpserver, directory, filename, quality_label = resolved
        dest_path = dest_dir / filename

        # Skip download if file already exists and is non-empty
        if dest_path.exists() and dest_path.stat().st_size > 0:
            # Still attempt to get the MD5 sidecar alongside it
            ftp_try_download_md5_sidecar(ftpserver, directory, filename, dest_dir)
            return (dest_path, server_name, quality_label)

        success = ftp_download_file(ftpserver, directory, filename, dest_path)
        if not success:
            continue

        # Try to grab MD5 sidecar (best-effort, non-blocking)
        ftp_try_download_md5_sidecar(ftpserver, directory, filename, dest_dir)

        return (dest_path, server_name, quality_label)

    return None


# ---------------------------------------------------------------------------
# Broadcast navigation — single source path (no quality collection)
# ---------------------------------------------------------------------------


def download_broadcast_nav_with_fallback(
    source_map: dict[str, ProductSourcesFTP],
    dest_dir: Path,
    server_priority: list[str] = SERVER_PRIORITY,
) -> Optional[tuple[Path, str, str]]:
    """
    Download broadcast navigation files.

    Strategy: RINEX 3 multi-system file preferred (``broadcast_rnx3``).
    Falls back to downloading RINEX 2 GPS + GLONASS files and merging them
    into a BRDM file when RINEX 3 is not available.

    Returns
    -------
    (local_path, server_name, format_label) or *None*
    """
    dest_dir.mkdir(parents=True, exist_ok=True)

    # --- Attempt RINEX 3 ---
    for server_name in server_priority:
        if server_name not in source_map:
            continue
        sources: ProductSourcesFTP = source_map[server_name]
        rnx3: ProductSourcePathFTP = sources.broadcast_rnx3

        dir_listing = ftp_list_directory(rnx3.ftpserver, rnx3.directory)
        if not dir_listing:
            continue

        filename = find_best_match_in_listing(dir_listing, rnx3.file_regex)
        if filename is None:
            continue

        dest_path = dest_dir / filename
        if dest_path.exists() and dest_path.stat().st_size > 0:
            ftp_try_download_md5_sidecar(rnx3.ftpserver, rnx3.directory, filename, dest_dir)
            return (dest_path, server_name, "RINEX3")

        if ftp_download_file(rnx3.ftpserver, rnx3.directory, filename, dest_path):
            ftp_try_download_md5_sidecar(rnx3.ftpserver, rnx3.directory, filename, dest_dir)
            return (dest_path, server_name, "RINEX3")

    # --- Fall back to RINEX 2 GPS + GLONASS merge ---
    for server_name in server_priority:
        if server_name not in source_map:
            continue
        sources: ProductSourcesFTP = source_map[server_name]
        rnx2 = sources.broadcast_rnx2

        # Determine shared directory from GPS source
        gps_src: ProductSourcePathFTP = rnx2.gps
        glonass_src: ProductSourcePathFTP = rnx2.glonass

        dir_listing = ftp_list_directory(gps_src.ftpserver, gps_src.directory)
        if not dir_listing:
            continue

        gps_file = find_best_match_in_listing(dir_listing, gps_src.file_regex)
        glonass_file = find_best_match_in_listing(dir_listing, glonass_src.file_regex)

        if gps_file is None or glonass_file is None:
            continue

        gps_dest = dest_dir / gps_file
        glonass_dest = dest_dir / glonass_file

        gps_ok = (
            (gps_dest.exists() and gps_dest.stat().st_size > 0)
            or ftp_download_file(gps_src.ftpserver, gps_src.directory, gps_file, gps_dest)
        )
        glonass_ok = (
            (glonass_dest.exists() and glonass_dest.stat().st_size > 0)
            or ftp_download_file(
                glonass_src.ftpserver, glonass_src.directory, glonass_file, glonass_dest
            )
        )

        if not (gps_ok and glonass_ok):
            continue

        # Decompress if needed
        gps_decompressed = _decompress_if_needed(gps_dest)
        glonass_decompressed = _decompress_if_needed(glonass_dest)

        if gps_decompressed is None or glonass_decompressed is None:
            continue

        brdm = _merge_rinex2_nav(gps_decompressed, glonass_decompressed, dest_dir)
        if brdm is not None:
            return (brdm, server_name, "BRDM-RINEX2")

    return None


# ---------------------------------------------------------------------------
# RINEX 2 merge helper (ported from pride_tools/gnss_product_operations.py)
# ---------------------------------------------------------------------------


def _decompress_if_needed(path: Path) -> Optional[Path]:
    """Decompress a .gz file in-place. Returns the decompressed path or *path* if not gzip."""
    if path.suffix != ".gz":
        return path
    out = path.with_suffix("")
    try:
        with gzip.open(path, "rb") as f_in, open(out, "wb") as f_out:
            while chunk := f_in.read(65_536):
                f_out.write(chunk)
        path.unlink(missing_ok=True)
        return out
    except Exception:  # noqa: BLE001
        out.unlink(missing_ok=True)
        return None


def _merge_rinex2_nav(brdn: Path, brdg: Path, output_folder: Path) -> Optional[Path]:
    """
    Merge GPS (.n) and GLONASS (.g) RINEX 2 broadcast nav files into a
    single BRDM (.p) file compatible with PRIDE-PPP.

    Ported from ``pride_tools.gnss_product_operations.merge_broadcast_files``.
    """
    # Derive output filename from GPS file: brdc{DDD}0.{YY}p
    try:
        ddd = brdn.name[4:7]
        yy = brdn.name[9:11]
    except IndexError:
        return None

    brdm = output_folder / f"brdm{ddd}0.{yy}p"

    def _parse_brdn(
        lines: list[str], prefix: str, out: io.StringIO
    ) -> None:
        in_header = True
        i = 1
        while i < len(lines):
            try:
                if not in_header:
                    line = lines[i].replace("D", "e")
                    prn = int(line[0:2])
                    yyyy = int(line[3:5]) + 2000
                    mm, dd, hh, mi = int(line[6:8]), int(line[9:11]), int(line[12:14]), int(line[15:17])
                    ss = round(float(line[18:22]))
                    n2, n3, n4 = float(eval(line[22:41])), float(eval(line[41:60])), float(eval(line[60:79]))
                    out.write(f"{prefix}{prn:02d} {yyyy:04d} {mm:02d} {dd:02d} {hh:02d} {mi:02d} {ss:02d} {n2:.12e} {n3:.12e} {n4:.12e}\n")
                    for t in range(1, 4):
                        l2 = lines[i + t].replace("D", "e")
                        a, b, c, d_ = float(eval(l2[3:22])), float(eval(l2[22:41])), float(eval(l2[41:60])), float(eval(l2[60:79]))
                        out.write(f"    {a:.12e} {b:.12e} {c:.12e} {d_:.12e}\n")
                    l7 = lines[i + 7].replace("D", "e")
                    a, b = float(eval(l7[3:22])), float(eval(l7[22:41]))
                    out.write(f"    {a:.12e} {b:.12e}\n")
                    i += 8
                else:
                    if "PGM / RUN BY / DATE" in lines[i][60:79]:
                        out.write(lines[i])
                    if "LEAP SECONDS" in lines[i][60:72]:
                        out.write(lines[i])
                    if "END OF HEADER" in lines[i][60:73]:
                        in_header = False
                        out.write(lines[i])
                    i += 1
            except Exception:  # noqa: BLE001
                break

    def _parse_brdg(lines: list[str], out: io.StringIO) -> None:
        in_header = True
        i = 1
        while i < len(lines):
            try:
                if not in_header:
                    line = lines[i].replace("D", "e")
                    prn = int(line[0:2])
                    yyyy = int(line[3:5]) + 2000
                    mm, dd, hh, mi = int(line[6:8]), int(line[9:11]), int(line[12:14]), int(line[15:17])
                    ss = round(float(line[18:22]))
                    n2, n3, n4 = float(eval(line[22:41])), float(eval(line[41:60])), float(eval(line[60:79]))
                    out.write(f"R{prn:02d} {yyyy:04d} {mm:02d} {dd:02d} {hh:02d} {mi:02d} {int(ss):02d}{n2: .12e}{n3: .12e}{n4: .12e}\n")
                    for t in range(1, 4):
                        l2 = lines[i + t].replace("D", "e")
                        a, b, c, d_ = float(eval(l2[3:22])), float(eval(l2[22:41])), float(eval(l2[41:60])), float(eval(l2[60:79]))
                        out.write(f"    {a: .12e}{b: .12e}{c: .12e}{d_: .12e}\n")
                    i += 4
                else:
                    if "END OF HEADER" in lines[i][60:73]:
                        in_header = False
                    i += 1
            except Exception:  # noqa: BLE001
                break

    try:
        buf = io.StringIO()
        buf.write("     3.04           NAVIGATION DATA     M (Mixed)           RINEX VERSION / TYPE\n")
        _parse_brdn(brdn.read_text().splitlines(keepends=True), "G", buf)
        _parse_brdg(brdg.read_text().splitlines(keepends=True), buf)
        brdm.write_text(buf.getvalue())
        return brdm if brdm.exists() and brdm.stat().st_size > 0 else None
    except Exception:  # noqa: BLE001
        brdm.unlink(missing_ok=True)
        return None
