"""Unit tests for ConnectionPool dead-connection and pool-shrink behaviour.

Regression tests for the bug where replace_connection() was a no-op and
dead connections were silently re-inserted into the pool by get_connection's
finally block, causing unbounded retry noise and a never-shrinking pool.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest
from gnss_product_management.factories.connection_pool import (
    ConnectionPool,
    ConnectionPoolFactory,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pool(n: int) -> ConnectionPool:
    """Return a pre-initialised pool with *n* mock connections."""
    pool = ConnectionPool("ftp://test.example.com", max_connections=n)
    mock_connections = [MagicMock(name=f"conn_{i}") for i in range(n)]
    pool._pool = list(mock_connections)
    pool._semaphore = threading.Semaphore(n)
    pool._initialized = True
    return pool, mock_connections


# ---------------------------------------------------------------------------
# replace_connection: reconnect succeeds
# ---------------------------------------------------------------------------


class TestReplaceConnectionSuccess:
    def test_dead_not_reinserted_in_pool(self):
        """Dead connection must not be appended back after a successful replace."""
        pool, (dead,) = _make_pool(1)

        fresh = MagicMock(name="fresh")
        with patch.object(pool, "_connect", return_value=fresh):
            with pool.get_connection() as conn:
                assert conn is dead
                result = pool.replace_connection(conn)

        assert result is fresh
        assert dead not in pool._pool
        assert fresh in pool._pool

    def test_pool_size_unchanged_after_successful_replace(self):
        """Pool size should remain the same when replace succeeds."""
        pool, (dead, _other) = _make_pool(2)

        fresh = MagicMock(name="fresh")
        with patch.object(pool, "_connect", return_value=fresh):
            with pool.get_connection() as conn:
                pool.replace_connection(conn)

        assert len(pool._pool) == 2
        assert dead not in pool._pool

    def test_semaphore_count_unchanged_after_successful_replace(self):
        """Semaphore count must remain consistent with pool size after replace."""
        pool, (dead, _other) = _make_pool(2)
        initial_sem = pool._semaphore._value

        fresh = MagicMock(name="fresh")
        with patch.object(pool, "_connect", return_value=fresh):
            with pool.get_connection() as conn:
                pool.replace_connection(conn)

        assert pool._semaphore._value == initial_sem


# ---------------------------------------------------------------------------
# replace_connection: reconnect fails
# ---------------------------------------------------------------------------


class TestReplaceConnectionFailure:
    def test_dead_not_reinserted_in_pool(self):
        """Dead connection must NOT be appended back when reconnect fails."""
        pool, (dead,) = _make_pool(1)

        with patch.object(pool, "_connect", return_value=None):
            with pool.get_connection() as conn:
                assert conn is dead
                result = pool.replace_connection(conn)

        assert result is None
        assert dead not in pool._pool

    def test_pool_shrinks_by_one_after_failed_reconnect(self):
        """Pool must shrink by 1 when the dead connection cannot be replaced."""
        pool, (_dead, _other) = _make_pool(2)

        with patch.object(pool, "_connect", return_value=None):
            with pool.get_connection() as conn:
                pool.replace_connection(conn)

        assert len(pool._pool) == 1

    def test_semaphore_shrinks_by_one_after_failed_reconnect(self):
        """Semaphore count must drop by 1 when reconnect fails (pool truly shrinks)."""
        pool, (_dead, _other) = _make_pool(2)
        initial_sem = pool._semaphore._value  # 2

        with patch.object(pool, "_connect", return_value=None):
            with pool.get_connection() as conn:
                pool.replace_connection(conn)

        # After consuming 1 slot and not releasing it, sem should be initial - 1
        assert pool._semaphore._value == initial_sem - 1

    def test_pool_marked_failed_when_last_connection_exhausted(self):
        """Pool must be marked _failed when all connections are exhausted."""
        pool, (_dead,) = _make_pool(1)

        with patch.object(pool, "_connect", return_value=None):
            with pool.get_connection() as conn:
                pool.replace_connection(conn)

        assert pool._failed is True
        assert pool._initialized is False

    def test_get_connection_raises_after_pool_exhausted(self):
        """get_connection() must raise ConnectionError after full exhaustion."""
        pool, (_dead,) = _make_pool(1)

        with patch.object(pool, "_connect", return_value=None):
            with pool.get_connection() as conn:
                pool.replace_connection(conn)

        # Pool is now failed; next call should raise immediately
        with pytest.raises(ConnectionError):
            with pool.get_connection():
                pass

    def test_multiple_failed_reconnects_shrink_pool_correctly(self):
        """Each failed reconnect must shrink pool by exactly 1."""
        pool, (a, b, c) = _make_pool(3)

        with patch.object(pool, "_connect", return_value=None):
            # First failure
            with pool.get_connection() as conn1:
                pool.replace_connection(conn1)
            assert len(pool._pool) == 2

            # Second failure
            with pool.get_connection() as conn2:
                pool.replace_connection(conn2)
            assert len(pool._pool) == 1

            # Third failure — pool exhausted
            with pool.get_connection() as conn3:
                pool.replace_connection(conn3)
            assert len(pool._pool) == 0
            assert pool._failed is True


# ---------------------------------------------------------------------------
# list_directory integration (via ConnectionPoolFactory)
# ---------------------------------------------------------------------------


class TestListDirectoryWithDeadConnections:
    def _make_factory_with_mock_pool(self, pool: ConnectionPool) -> ConnectionPoolFactory:
        factory = ConnectionPoolFactory()
        factory._pools["ftp://test.example.com"] = pool
        return factory

    def test_returns_empty_list_when_all_connections_fail(self):
        """list_directory must return [] gracefully when reconnect repeatedly fails."""
        pool, (dead,) = _make_pool(1)

        # Both initial ls and retry fail
        dead.ls.side_effect = OSError("timed out")
        factory = self._make_factory_with_mock_pool(pool)

        with patch.object(pool, "_connect", return_value=None):
            result = factory.list_directory("ftp://test.example.com", "/pub/products/2208/")

        assert result == []

    def test_no_stale_connections_after_failed_reconnect(self):
        """After a failed reconnect, the dead connection must not remain in pool."""
        pool, (dead,) = _make_pool(1)
        dead.ls.side_effect = OSError("connection reset")
        factory = self._make_factory_with_mock_tool(pool)

        with patch.object(pool, "_connect", return_value=None):
            factory.list_directory("ftp://test.example.com", "/pub/products/2208/")

        assert dead not in pool._pool

    def _make_factory_with_mock_tool(self, pool: ConnectionPool) -> ConnectionPoolFactory:
        return self._make_factory_with_mock_pool(pool)
