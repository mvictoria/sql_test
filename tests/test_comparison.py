from sql_test.testing.cases import CaseTable
from sql_test.testing.comparison import Change, compare

ADA = {"member_id": 1, "member_name": "Ada"}
BEA = {"member_id": 2, "member_name": "Bea"}


def _expected(*rows):
    return CaseTable(columns=("member_id", "member_name"), rows=list(rows))


def test_rows_in_both_match_in_any_order():
    comparison = compare(_expected(ADA, BEA), [BEA, ADA])

    assert comparison.matched == [ADA, BEA]
    assert comparison.passed


def test_a_row_with_some_values_different_is_changed():
    actual = {"member_id": 1, "member_name": "Adaline"}

    comparison = compare(_expected(ADA), [actual])

    assert comparison.changed == [
        Change(expected=ADA, actual=actual, columns=("member_name",))
    ]
    assert not comparison.passed


def test_an_expected_row_not_in_actual_is_missing():
    comparison = compare(_expected(ADA, BEA), [ADA])

    assert comparison.missing == [BEA]
    assert not comparison.passed


def test_an_actual_row_not_expected_is_unexpected():
    comparison = compare(_expected(ADA), [ADA, BEA])

    assert comparison.unexpected == [BEA]
    assert not comparison.passed


def test_duplicates_count():
    comparison = compare(_expected(ADA), [ADA, ADA])

    assert comparison.matched == [ADA]
    assert comparison.unexpected == [ADA]


def test_only_listed_columns_are_checked():
    comparison = compare(
        CaseTable(columns=("member_id",), rows=[{"member_id": 1}]),
        [{"member_id": 1, "member_name": "Ada"}],
    )

    assert comparison.passed


def test_a_listed_column_the_output_lacks_fails():
    comparison = compare(
        CaseTable(columns=("member_id", "lob"), rows=[{"member_id": 1, "lob": "30"}]),
        [ADA],
    )

    assert comparison.missing_columns == ("lob",)
    assert not comparison.passed


def test_null_matches_null():
    row = {"member_id": 1, "member_name": None}

    assert compare(_expected(row), [row]).passed


def test_ordered_rows_must_appear_in_order():
    comparison = compare(_expected(ADA, BEA), [BEA, ADA], ordered=True)

    assert not comparison.passed
    assert compare(_expected(ADA, BEA), [ADA, BEA], ordered=True).passed
