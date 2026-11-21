from dataclasses import dataclass, field

from sql_test.engine.executor import Row
from sql_test.testing.cases import CaseTable


@dataclass(frozen=True)
class Change:
    expected: Row
    actual: Row
    columns: tuple[str, ...]


@dataclass
class Comparison:
    matched: list[Row] = field(default_factory=list)
    changed: list[Change] = field(default_factory=list)
    missing: list[Row] = field(default_factory=list)
    unexpected: list[Row] = field(default_factory=list)
    missing_columns: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return not (
            self.changed or self.missing or self.unexpected or self.missing_columns
        )


def compare(
    expected: CaseTable, actual: list[Row], ordered: bool = False
) -> Comparison:
    output_columns = set().union(*actual) if actual else set(expected.columns)
    columns = tuple(name for name in expected.columns if name in output_columns)
    comparison = Comparison(
        missing_columns=tuple(
            name for name in expected.columns if name not in output_columns
        )
    )
    wanted = [_project(row, columns) for row in expected.rows]
    got = [_project(row, columns) for row in actual]
    if ordered:
        for want, have in zip(wanted, got, strict=False):
            if want == have:
                comparison.matched.append(want)
            else:
                _pair([want], [have], columns, comparison)
        _pair(wanted[len(got) :], got[len(wanted) :], columns, comparison)
    else:
        leftover = list(got)
        unmatched = []
        for want in wanted:
            if want in leftover:
                leftover.remove(want)
                comparison.matched.append(want)
            else:
                unmatched.append(want)
        _pair(unmatched, leftover, columns, comparison)
    return comparison


def _project(row: Row, columns: tuple[str, ...]) -> Row:
    return {name: row.get(name) for name in columns}


def _pair(
    wanted: list[Row], got: list[Row], columns: tuple[str, ...], comparison: Comparison
) -> None:
    """Report rows agreeing on at least half of several columns as changed."""
    leftover = list(got)
    for want in wanted:
        best, differing = None, columns
        for have in leftover:
            different = tuple(name for name in columns if want[name] != have[name])
            if len(different) < len(differing):
                best, differing = have, different
        if best is not None and len(columns) > 1 and 2 * len(differing) <= len(columns):
            leftover.remove(best)
            comparison.changed.append(
                Change(expected=want, actual=best, columns=differing)
            )
        else:
            comparison.missing.append(want)
    comparison.unexpected.extend(leftover)
