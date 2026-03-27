"""
Tests: FTP connectivity via ftp_can_connect and _ftp_connect.

Verifies that the shared connection helper can reach known GNSS data
servers (Wuhan FTP, CODE FTP, CDDIS FTPS) and correctly handles
unreachable hosts.

These tests hit real FTP servers and are marked ``integration``.
"""
from __future__ import annotations

import pytest

from gnss_ppp_products.server.ftp import ftp_can_connect, _ftp_connect


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
        assert ftp_can_connect(
            "ftps://gdc.cddis.eosdis.nasa.gov", timeout=15, use_tls=True
        ) is True

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


# ---------------------------------------------------------------------------
# Integration: connectivity cache in ResourceFetcher
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestResourceFetcherConnectivity:
    """Verify that ResourceFetcher's connectivity cache works."""

    def test_connectivity_cache_populated(self, fetcher) -> None:
        """After listing a directory, the connectivity cache should record success."""
        from gnss_ppp_products.factories.resource_fetcher import ResourceFetcher

        fresh = ResourceFetcher()
        # Trigger a listing that uses ftp_can_connect internally
        listing = fresh._list_ftp("ftp://ftp.aiub.unibe.ch", "CODE/2025")
        assert len(listing) > 0
        # Cache key is built as "ftp://{hostname}" where hostname may include scheme
        assert any("ftp.aiub.unibe.ch" in k for k in fresh._connectivity_cache)
        assert all(v is True for v in fresh._connectivity_cache.values())

    def test_connectivity_cache_prevents_retry(self, fetcher) -> None:
        """A failed server should be cached and raise immediately on retry."""
        from gnss_ppp_products.factories.resource_fetcher import ResourceFetcher

        fresh = ResourceFetcher()
        # Force failure
        try:
            fresh._list_ftp("ftp://nonexistent.invalid.host", "/")
        except ConnectionError:
            pass
        # Verify failure is cached
        assert any("nonexistent.invalid.host" in k for k in fresh._connectivity_cache)
        assert any(v is False for v in fresh._connectivity_cache.values())

        # Second attempt should raise from cache
        with pytest.raises(ConnectionError, match="cached"):
            fresh._list_ftp("ftp://nonexistent.invalid.host", "/some/dir")
