from collections.abc import Iterable

from sql_test.testing.cases import CaseSummary


def case_counts(tables: Iterable[str], cases: Iterable[CaseSummary]) -> dict[str, int]:
    """How many discovered cases target each table, including zero."""
    counts = {name: 0 for name in tables}
    for case in cases:
        counts[case.target] = counts.get(case.target, 0) + 1
    return counts
