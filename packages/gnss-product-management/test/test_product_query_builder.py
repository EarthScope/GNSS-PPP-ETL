"""Tests for ProductQuery fluent builder — immutable-clone pattern.

These are pure unit tests: no network calls, no filesystem access.
WormHole and SearchPlanner are replaced with simple mocks because the
builder tests only verify state, not execution.
"""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock

import pytest
from gnss_product_management.client.product_query import ProductQuery

# ── Fixtures ───────────────────────────────────────────────────────────


DATE_A = datetime.datetime(2025, 1, 15, tzinfo=datetime.timezone.utc)
DATE_B = datetime.datetime(2025, 2, 20, tzinfo=datetime.timezone.utc)


def _query() -> ProductQuery:
    """Return a fresh ProductQuery with mock dependencies."""
    return ProductQuery(wormhole=MagicMock(), search_planner=MagicMock())


# ── for_product ───────────────────────────────────────────────────────


class TestForProduct:
    def test_returns_new_instance(self) -> None:
        q = _query()
        q2 = q.for_product("ORBIT")
        assert q2 is not q

    def test_original_unchanged(self) -> None:
        q = _query()
        q.for_product("ORBIT")
        assert q._product is None

    def test_string_product_stored_as_dict(self) -> None:
        q = _query().for_product("ORBIT")
        assert q._product == {"name": "ORBIT"}

    def test_dict_product_stored_as_is(self) -> None:
        q = _query().for_product({"name": "ORBIT", "version": "1"})
        assert q._product == {"name": "ORBIT", "version": "1"}

    def test_last_call_wins(self) -> None:
        q = _query().for_product("ORBIT").for_product("CLOCK")
        assert q._product == {"name": "CLOCK"}


# ── on ────────────────────────────────────────────────────────────────


class TestOn:
    def test_returns_new_instance(self) -> None:
        q = _query()
        q2 = q.on(DATE_A)
        assert q2 is not q

    def test_original_unchanged(self) -> None:
        q = _query()
        q.on(DATE_A)
        assert q._date is None

    def test_date_set(self) -> None:
        q = _query().on(DATE_A)
        assert q._date == DATE_A

    def test_last_call_wins(self) -> None:
        q = _query().on(DATE_A).on(DATE_B)
        assert q._date == DATE_B


# ── on_range ──────────────────────────────────────────────────────────


class TestOnRange:
    def test_returns_new_instance(self) -> None:
        q = _query()
        q2 = q.on_range(DATE_A, DATE_B)
        assert q2 is not q

    def test_range_stored(self) -> None:
        q = _query().on_range(DATE_A, DATE_B)
        assert q._date_range is not None
        start, end, step = q._date_range
        assert start == DATE_A
        assert end == DATE_B

    def test_on_range_clears_single_date(self) -> None:
        q = _query().on(DATE_A).on_range(DATE_A, DATE_B)
        assert q._date is None

    def test_start_after_end_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be after"):
            _query().on_range(DATE_B, DATE_A)


# ── where ─────────────────────────────────────────────────────────────


class TestWhere:
    def test_returns_new_instance(self) -> None:
        q = _query()
        q2 = q.where(TTT="FIN")
        assert q2 is not q

    def test_original_unchanged(self) -> None:
        q = _query()
        q.where(TTT="FIN")
        assert q._parameters == {}

    def test_parameters_set(self) -> None:
        q = _query().where(TTT="FIN", AAA="WUM")
        assert q._parameters["TTT"] == "FIN"
        assert q._parameters["AAA"] == "WUM"

    def test_chained_where_accumulates(self) -> None:
        q = _query().where(TTT="FIN").where(AAA="WUM")
        assert q._parameters["TTT"] == "FIN"
        assert q._parameters["AAA"] == "WUM"


# ── sources ───────────────────────────────────────────────────────────


class TestSources:
    def test_returns_new_instance(self) -> None:
        q = _query()
        q2 = q.sources("COD")
        assert q2 is not q

    def test_original_unchanged(self) -> None:
        q = _query()
        q.sources("COD")
        assert q._source_ids is None

    def test_ids_stored(self) -> None:
        q = _query().sources("COD", "ESA")
        assert "COD" in q._source_ids
        assert "ESA" in q._source_ids

    def test_no_args_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one resource ID"):
            _query().sources()

    def test_last_call_wins(self) -> None:
        q = _query().sources("COD").sources("ESA")
        assert "ESA" in q._source_ids
        assert "COD" not in q._source_ids


# ── prefer ────────────────────────────────────────────────────────────


class TestPrefer:
    def test_returns_new_instance(self) -> None:
        q = _query()
        q2 = q.prefer(TTT=["FIN", "RAP"])
        assert q2 is not q

    def test_original_unchanged(self) -> None:
        q = _query()
        q.prefer(TTT=["FIN", "RAP"])
        assert q._preferences == []

    def test_preference_added(self) -> None:
        q = _query().prefer(TTT=["FIN", "RAP"])
        assert len(q._preferences) == 1
        assert q._preferences[0].parameter == "TTT"
        assert q._preferences[0].sorting == ["FIN", "RAP"]

    def test_chained_prefer_accumulates(self) -> None:
        q = _query().prefer(TTT=["FIN", "RAP"]).prefer(AAA=["WUM", "COD"])
        assert len(q._preferences) == 2
        params = [p.parameter for p in q._preferences]
        assert "TTT" in params
        assert "AAA" in params

    def test_string_sorting_wrapped_in_list(self) -> None:
        q = _query().prefer(TTT="FIN")
        assert q._preferences[0].sorting == ["FIN"]


# ── search validation ─────────────────────────────────────────────────


class TestSearchValidation:
    def test_search_without_product_raises(self) -> None:
        q = _query().on(DATE_A)
        with pytest.raises(ValueError, match="for_product"):
            q.search()

    def test_search_without_date_raises(self) -> None:
        q = _query().for_product("ORBIT")
        with pytest.raises(ValueError, match="on"):
            q.search()
