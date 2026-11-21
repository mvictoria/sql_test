"""TEST-1: property-based comparison (unordered multisets)."""

from hypothesis import given
from hypothesis import strategies as st

from sql_test.testing.cases import CaseTable
from sql_test.testing.comparison import compare

COLUMNS = ("a", "b")


def _table(rows: list[dict[str, int]]) -> CaseTable:
    return CaseTable(columns=COLUMNS, rows=list(rows))


row = st.fixed_dictionaries({"a": st.integers(0, 5), "b": st.integers(0, 5)})
rows = st.lists(row, max_size=8)


@given(rows)
def test_the_same_multiset_passes_in_any_order(bag: list[dict[str, int]]):
    shuffled = list(reversed(bag))
    assert compare(_table(bag), shuffled).passed


@given(rows.filter(lambda bag: len(bag) > 0))
def test_a_removed_row_fails_and_matches_only_what_remains(bag: list[dict[str, int]]):
    actual = list(bag)
    actual.pop()
    comparison = compare(_table(bag), actual)
    assert not comparison.passed
    assert len(comparison.matched) == len(actual)


@given(rows)
def test_an_extra_actual_row_is_unexpected(bag: list[dict[str, int]]):
    extra = {"a": 9, "b": 9}
    comparison = compare(_table(bag), [*bag, extra])
    assert not comparison.passed
    assert extra in comparison.unexpected
