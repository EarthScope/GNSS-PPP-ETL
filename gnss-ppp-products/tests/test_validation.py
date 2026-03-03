"""
Tests for gnss_ppp_products.utils.validation

All tests are offline — no FTP or network access required.
"""
from __future__ import annotations

import gzip
import hashlib
import io
from pathlib import Path

import pytest

from gnss_ppp_products.utils.validation import (
    ValidationResult,
    check_gzip_integrity,
    check_md5_checksum,
    check_nonzero_size,
    validate_product_file,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_gz(tmp_path: Path, name: str, content: bytes = b"GNSS data") -> Path:
    """Write valid gzip data to *tmp_path/<name>*."""
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
        gz.write(content)
    p = tmp_path / name
    p.write_bytes(buf.getvalue())
    return p


def _make_md5_sidecar(path: Path) -> Path:
    """Create a GNU-style ``<hex>  <name>`` MD5 sidecar next to *path*."""
    digest = hashlib.md5(path.read_bytes()).hexdigest()
    sidecar = path.parent / (path.name + ".md5")
    sidecar.write_text(f"{digest}  {path.name}\n", encoding="ascii")
    return sidecar


# ---------------------------------------------------------------------------
# check_nonzero_size
# ---------------------------------------------------------------------------

class TestCheckNonzeroSize:
    def test_missing_file_returns_false(self, tmp_path):
        ok, msg = check_nonzero_size(tmp_path / "ghost.txt")
        assert ok is False
        assert "does not exist" in msg

    def test_empty_file_returns_false(self, tmp_path):
        p = tmp_path / "empty.SP3.gz"
        p.write_bytes(b"")
        ok, msg = check_nonzero_size(p)
        assert ok is False
        assert "zero" in msg

    def test_nonempty_file_returns_true(self, tmp_path):
        p = tmp_path / "data.clk"
        p.write_bytes(b"clock data")
        ok, _ = check_nonzero_size(p)
        assert ok is True


# ---------------------------------------------------------------------------
# check_gzip_integrity
# ---------------------------------------------------------------------------

class TestCheckGzipIntegrity:
    def test_valid_gz_returns_true(self, tmp_path):
        p = _make_gz(tmp_path, "orbit.SP3.gz")
        ok, _ = check_gzip_integrity(p)
        assert ok is True

    def test_corrupt_gz_returns_false(self, tmp_path):
        p = tmp_path / "corrupt.SP3.gz"
        # Valid gzip magic bytes but garbage body
        p.write_bytes(b"\x1f\x8b" + b"\xff" * 40)
        ok, msg = check_gzip_integrity(p)
        assert ok is False
        assert "gzip" in msg.lower()

    def test_non_gz_extension_is_skipped(self, tmp_path):
        p = tmp_path / "brdm3050.25p"
        p.write_bytes(b"RINEX nav data")
        ok, msg = check_gzip_integrity(p)
        assert ok is True
        assert "skip" in msg.lower()

    def test_gz_extension_with_truncated_content(self, tmp_path):
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
            gz.write(b"A" * 1_000)
        data = buf.getvalue()
        # Truncate the compressed stream
        p = tmp_path / "truncated.ERP.gz"
        p.write_bytes(data[: len(data) // 2])
        ok, _ = check_gzip_integrity(p)
        assert ok is False


# ---------------------------------------------------------------------------
# check_md5_checksum
# ---------------------------------------------------------------------------

class TestCheckMd5Checksum:
    def test_correct_gnu_format_passes(self, tmp_path):
        p = tmp_path / "orbit.SP3.gz"
        p.write_bytes(b"SP3 orbit content")
        sidecar = _make_md5_sidecar(p)
        ok, _ = check_md5_checksum(p, sidecar)
        assert ok is True

    def test_wrong_checksum_fails(self, tmp_path):
        p = tmp_path / "clock.CLK.gz"
        p.write_bytes(b"clock data")
        sidecar = p.parent / (p.name + ".md5")
        sidecar.write_text("deadbeef00000000000000000000dead  clock.CLK.gz\n", encoding="ascii")
        ok, msg = check_md5_checksum(p, sidecar)
        assert ok is False
        assert "mismatch" in msg.lower()

    def test_missing_sidecar_silently_passes(self, tmp_path):
        p = tmp_path / "bias.BIA.gz"
        p.write_bytes(b"bias data")
        ok, msg = check_md5_checksum(p, tmp_path / "bias.BIA.gz.md5")
        assert ok is True
        assert "skip" in msg.lower()

    def test_hex_only_sidecar_passes(self, tmp_path):
        """Sidecar contains only the hex digest (no filename)."""
        p = tmp_path / "erp.ERP.gz"
        p.write_bytes(b"erp data")
        digest = hashlib.md5(p.read_bytes()).hexdigest()
        sidecar = p.parent / (p.name + ".md5")
        sidecar.write_text(f"{digest}\n", encoding="ascii")
        ok, _ = check_md5_checksum(p, sidecar)
        assert ok is True


# ---------------------------------------------------------------------------
# validate_product_file (integration of all checks)
# ---------------------------------------------------------------------------

class TestValidateProductFile:
    def test_valid_gz_no_sidecar(self, tmp_path):
        p = _make_gz(tmp_path, "WMC0DEMFIN_20253050000_01D_05M_ORB.SP3.gz")
        result = validate_product_file(p)
        assert result.is_valid
        assert result.checks["nonzero_size"] is True
        assert result.checks["gzip_integrity"] is True
        assert "md5_checksum" not in result.checks

    def test_valid_gz_with_md5_sidecar(self, tmp_path):
        p = _make_gz(tmp_path, "orbit.SP3.gz")
        sidecar = _make_md5_sidecar(p)
        result = validate_product_file(p, sidecar)
        assert result.is_valid
        assert result.checks["md5_checksum"] is True

    def test_empty_file_short_circuits_before_gzip_check(self, tmp_path):
        p = tmp_path / "empty.SP3.gz"
        p.write_bytes(b"")
        result = validate_product_file(p)
        assert not result.is_valid
        assert result.checks["nonzero_size"] is False
        # Gzip check must be skipped on short-circuit
        assert "gzip_integrity" not in result.checks
        assert result.errors

    def test_corrupt_gz_fails_gzip_check(self, tmp_path):
        p = tmp_path / "bad.CLK.gz"
        p.write_bytes(b"\x1f\x8b" + b"\x00" * 30)
        result = validate_product_file(p)
        assert not result.is_valid
        assert result.checks["gzip_integrity"] is False
        assert result.errors

    def test_bad_md5_makes_result_invalid(self, tmp_path):
        p = _make_gz(tmp_path, "erp.ERP.gz")
        sidecar = p.parent / (p.name + ".md5")
        sidecar.write_text("000000000000000000000000deadbeef  erp.ERP.gz\n", encoding="ascii")
        result = validate_product_file(p, sidecar)
        assert not result.is_valid
        assert result.checks["nonzero_size"] is True
        assert result.checks["gzip_integrity"] is True
        assert result.checks["md5_checksum"] is False

    def test_non_gz_file_skips_gzip_check(self, tmp_path):
        p = tmp_path / "brdm3050.25p"
        p.write_bytes(b"RINEX nav data")
        result = validate_product_file(p)
        assert result.is_valid
        assert result.checks["gzip_integrity"] is True  # skip = pass

    def test_result_path_attribute(self, tmp_path):
        p = _make_gz(tmp_path, "orbit.SP3.gz")
        result = validate_product_file(p)
        assert result.path == p
