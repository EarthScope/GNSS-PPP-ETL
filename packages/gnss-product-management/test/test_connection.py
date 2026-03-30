"""
Tests: FTP connectivity via ftp_can_connect and _ftp_connect.

Verifies that the shared connection helper can reach known GNSS data
servers (Wuhan FTP, CODE FTP, CDDIS FTPS) and correctly handles
unreachable hosts.

These tests hit real FTP servers and are marked ``integration``.
"""

from __future__ import annotations

import pytest

from gnss_product_management.server.ftp import ftp_can_connect, _ftp_connect


# ---------------------------------------------------------------------------
# Integration: reach real servers
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestFtpCanConnect:
    """Verify ftp_can_connect against live servers."""

    def test_wuhan_ftp_reachable(self) -> None:
        assert ftp_can_connect("ftp://igs.gnsswhu.cn", timeout=15) is True

    def test_code_ftp_reachable(self) -> None:
        assert ftp_can_connect("ftp://ftp.aiub.unibe.ch", timeout=15) is True

    def test_cddis_ftps_reachable(self) -> None:
        assert (
            ftp_can_connect(
                "ftps://gdc.cddis.eosdis.nasa.gov", timeout=15, use_tls=True
            )
            is True
        )

    def test_hostname_prefix_stripped(self) -> None:
        """ftp:// and ftps:// prefixes must be stripped before connecting."""
        assert ftp_can_connect("ftp://ftp.aiub.unibe.ch", timeout=15) is True

    def test_unreachable_host_returns_false(self) -> None:
        assert ftp_can_connect("ftp://nonexistent.invalid.host", timeout=5) is False


# ---------------------------------------------------------------------------
# Integration: _ftp_connect context manager
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestFtpConnectContextManager:
    """Verify _ftp_connect yields an authenticated connection."""

    def test_yields_ftp_object(self) -> None:
        with _ftp_connect("ftp://ftp.aiub.unibe.ch", timeout=15) as ftp:
            # Should be an open, authenticated connection
            response = ftp.pwd()
            assert isinstance(response, str)

    def test_tls_connection(self) -> None:
        with _ftp_connect(
            "ftps://gdc.cddis.eosdis.nasa.gov", timeout=15, use_tls=True
        ) as ftp:
            response = ftp.pwd()
            assert isinstance(response, str)

    def test_raises_on_unreachable(self) -> None:
        with pytest.raises(ConnectionError, match="All FTP connection attempts failed"):
            with _ftp_connect("ftp://nonexistent.invalid.host", timeout=5):
                pass  # pragma: no cover
