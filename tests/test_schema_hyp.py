"""TEST-1: Column.cast round-trip through case CSV cell text."""

from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from sql_test.engine.schema import Column
from sql_test.testing.cases.folder import _text


def _round_trip(column: Column, value: object) -> object:
    return column.cast(_text(value))


@given(st.integers(min_value=-(10**9), max_value=10**9))
def test_integers_round_trip_through_cell_text(value: int):
    assert _round_trip(Column(name="n", type="INT"), value) == value


@given(st.text(max_size=40))
def test_varchar_round_trips_through_cell_text(value: str):
    assert _round_trip(Column(name="s", type="VARCHAR"), value) == value


@given(st.booleans())
def test_booleans_round_trip_through_cell_text(value: bool):
    assert _round_trip(Column(name="b", type="BOOLEAN"), value) is value


@given(st.dates(min_value=date(1970, 1, 1), max_value=date(2100, 12, 31)))
def test_dates_round_trip_through_cell_text(value: date):
    assert _round_trip(Column(name="d", type="DATE"), value) == value


@given(
    st.decimals(
        min_value=Decimal("-1e8"),
        max_value=Decimal("1e8"),
        places=4,
        allow_nan=False,
        allow_infinity=False,
    )
)
def test_decimals_round_trip_through_cell_text(value: Decimal):
    assert _round_trip(Column(name="x", type="DECIMAL"), value) == value


def test_null_round_trips_as_none():
    assert _round_trip(Column(name="n", type="INT"), None) is None


@given(st.from_regex(r"[A-Za-z]{1,8}", fullmatch=True))
def test_non_integer_text_raises_for_an_int_column(text: str):
    with pytest.raises(ValueError):
        Column(name="n", type="INT").cast(text)
