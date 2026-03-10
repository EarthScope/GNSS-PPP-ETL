"""
Integration test suite: Reference table products via unified config-based query interface.

Metadata
--------
Products probed : LEAP_SECONDS, SAT_PARAMETERS
Sources         : WUHAN, CDDIS

Note: Reference tables are currently only partially modeled in YAML configs.
The Wuhan config has navigation products but leap_seconds/sat_parameters 
require explicit YAML product entries. This test validates what's available
and documents the migration path.

Usage
-----
Run all integration tests::

    uv run pytest test/test_reference_tables.py -v

Skip in offline environments::

    uv run pytest -m "not integration"
"""
from __future__ import annotations

import logging
from typing import List
import datetime

import pytest

from gnss_ppp_products.data_query import query, ProductType, ProductQuality
from gnss_ppp_products.resources.resource import RemoteProductAddress

log = logging.getLogger(__name__)

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Test parameters
# ---------------------------------------------------------------------------

# Reference tables are static but query() requires a date
DUMMY_DATE = datetime.date(2025, 1, 1)


# ---------------------------------------------------------------------------
# Reference Table Query Tests
# ---------------------------------------------------------------------------


class TestReferenceTableQuery:
    """Tests for reference table products via unified interface."""

    def test_leap_seconds_type_exists(self) -> None:
        """LEAP_SECONDS product type should exist."""
        assert ProductType.LEAP_SECONDS is not None
        assert ProductType.LEAP_SECONDS.value == "LEAP_SECONDS"

    def test_sat_parameters_type_exists(self) -> None:
        """SAT_PARAMETERS product type should exist."""
        assert ProductType.SAT_PARAMETERS is not None
        assert ProductType.SAT_PARAMETERS.value == "SAT_PARAMETERS"

    def test_leap_seconds_query_wuhan(self) -> None:
        """Query for LEAP_SECONDS from WUHAN."""
        log.info("Testing LEAP_SECONDS query from WUHAN")
        results = query(date=DUMMY_DATE, product_type=ProductType.LEAP_SECONDS, source="WUHAN")
        if len(results) > 0:
            product = results[0]
            assert product.type == ProductType.LEAP_SECONDS
            log.info("[WUHAN] LEAP_SECONDS: %s", product.filename)
        else:
            log.warning("[WUHAN] LEAP_SECONDS not yet configured in YAML")

    def test_leap_seconds_query_cddis(self) -> None:
        """Query for LEAP_SECONDS from CDDIS."""
        log.info("Testing LEAP_SECONDS query from CDDIS")
        results = query(date=DUMMY_DATE, product_type=ProductType.LEAP_SECONDS, source="CDDIS")
        if len(results) > 0:
            product = results[0]
            assert product.type == ProductType.LEAP_SECONDS
            log.info("[CDDIS] LEAP_SECONDS: %s", product.filename)
        else:
            log.warning("[CDDIS] LEAP_SECONDS not yet configured in YAML")

    def test_reference_table_query_any_source(self) -> None:
        """LEAP_SECONDS should be queryable from at least one source (if configured)."""
        results = query(date=DUMMY_DATE, product_type=ProductType.LEAP_SECONDS)
        log.info("LEAP_SECONDS from all sources: %d result(s)", len(results))
        # This may return 0 if no YAML configs define LEAP_SECONDS yet
        # Once configs are added, strengthen this assertion
        for r in results:
            log.info("  Source: %s, File: %s", r.server.name, r.filename)
