"""
GNSS product file validation utilities.

Provides three sequential checks:
  1. Non-zero file size
  2. Gzip integrity  (only for .gz files)
  3. MD5 checksum    (only when a .md5 sidecar file is supplied)

Validation short-circuits on the first failure to avoid operating on corrupt data.
"""
from __future__ import annotations

import gzip
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ValidationResult:
    """Result of validating a single GNSS product file."""
    is_valid: bool
    path: Path
    checks: dict[str, bool] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Individual check functions — each returns (passed: bool, message: str)
# ---------------------------------------------------------------------------

def check_nonzero_size(path: Path) -> tuple[bool, str]:
    """Fail if the file does not exist or is zero bytes."""
    if not path.exists():
        return False, f"File does not exist: {path}"
    size = path.stat().st_size
    if size == 0:
        return False, f"File is zero bytes: {path}"
    return True, f"Size OK ({size:,} bytes)"


def check_gzip_integrity(path: Path) -> tuple[bool, str]:
    """
    For .gz files: stream the entire compressed content to detect truncation
    or corruption (BadGzipFile / EOFError).  Non-.gz files always pass.
    """
    if path.suffix != ".gz":
        return True, "Not a gzip file — skipping integrity check"
    try:
        with gzip.open(path, "rb") as fh:
            while fh.read(65_536):
                pass
        return True, "Gzip integrity OK"
    except (gzip.BadGzipFile, EOFError, OSError) as exc:
        return False, f"Gzip integrity check failed: {exc}"


def check_md5_checksum(path: Path, md5_sidecar: Path) -> tuple[bool, str]:
    """
    Compare the file's computed MD5 against the value in *md5_sidecar*.

    IGS standard format: ``<hex>  <filename>`` (BSD md5 style, two spaces).
    The check is tolerant of single-space or hex-only sidecars by always
    extracting the first whitespace-delimited token.

    Skips silently if *md5_sidecar* does not exist.
    """
    if not md5_sidecar.exists():
        return True, "No MD5 sidecar present — skipping"
    try:
        expected = md5_sidecar.read_text(encoding="ascii").strip().split()[0].lower()
        md5 = hashlib.md5()
        with open(path, "rb") as fh:
            while chunk := fh.read(65_536):
                md5.update(chunk)
        actual = md5.hexdigest().lower()
        if actual == expected:
            return True, f"MD5 OK: {actual}"
        return False, f"MD5 mismatch — expected {expected}, got {actual}"
    except Exception as exc:  # noqa: BLE001
        return False, f"MD5 check error: {exc}"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def validate_product_file(
    path: Path,
    md5_sidecar: Optional[Path] = None,
) -> ValidationResult:
    """
    Run all applicable validations on a downloaded GNSS product file.

    Parameters
    ----------
    path:
        Path to the downloaded file (may be compressed or decompressed).
    md5_sidecar:
        Optional path to a .md5 sidecar file alongside the download.
        If *None* or the file does not exist, the MD5 check is skipped.

    Returns
    -------
    ValidationResult
        ``is_valid`` is *True* only when every applicable check passes.
    """
    result = ValidationResult(is_valid=True, path=path)

    # 1 — Non-zero size (short-circuit on failure)
    passed, msg = check_nonzero_size(path)
    result.checks["nonzero_size"] = passed
    if not passed:
        result.errors.append(msg)
        result.is_valid = False
        return result

    # 2 — Gzip integrity
    passed, msg = check_gzip_integrity(path)
    result.checks["gzip_integrity"] = passed
    if not passed:
        result.errors.append(msg)
        result.is_valid = False

    # 3 — MD5 checksum
    if md5_sidecar is not None:
        passed, msg = check_md5_checksum(path, md5_sidecar)
        result.checks["md5_checksum"] = passed
        if not passed:
            result.errors.append(msg)
            result.is_valid = False

    return result
