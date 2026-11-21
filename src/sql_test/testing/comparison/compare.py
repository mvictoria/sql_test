from dataclasses import dataclass, field

from sql_test.engine import Row
from sql_test.testing.cases import CaseTable


@dataclass(frozen=True)
class Change:
    expected: Row
    actual: Row
    differing_columns: tuple[str, ...]


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
    output_columns = set().union(*actual) if actual else set()
    checked = expected.columns
    missing_columns = tuple(name for name in checked if name not in output_columns)
    comparison = Comparison(missing_columns=missing_columns)
    wanted = [_project(row, checked) for row in expected.rows]
    got = [_project(row, checked) for row in actual]
    if ordered:
        for want, have in zip(wanted, got, strict=False):
            if not missing_columns and want == have:
                comparison.matched.append(want)
            else:
                _classify_unmatched(
                    [want], [have], checked, set(missing_columns), comparison
                )
        _classify_unmatched(
            wanted[len(got) :],
            got[len(wanted) :],
            checked,
            set(missing_columns),
            comparison,
        )
    else:
        leftover = list(got)
        unmatched = []
        for want in wanted:
            # A listed column the output lacks fails the case; no row can match.
            if not missing_columns and want in leftover:
                leftover.remove(want)
                comparison.matched.append(want)
            else:
                unmatched.append(want)
        _classify_unmatched(
            unmatched, leftover, checked, set(missing_columns), comparison
        )
    return comparison


def _project(row: Row, columns: tuple[str, ...]) -> Row:
    return {name: row.get(name) for name in columns}


def _classify_unmatched(
    wanted: list[Row],
    got: list[Row],
    columns: tuple[str, ...],
    missing_columns: set[str],
    comparison: Comparison,
) -> None:
    """Report rows agreeing on at least half of several columns as changed."""
    leftover = list(got)
    for want in wanted:
        best, differing = None, columns
        for have in leftover:
            different = tuple(
                name
                for name in columns
                if name in missing_columns or want[name] != have[name]
            )
            if len(different) < len(differing):
                best, differing = have, different
        if best is not None and len(columns) > 1 and 2 * len(differing) <= len(columns):
            leftover.remove(best)
            comparison.changed.append(
                Change(expected=want, actual=best, differing_columns=differing)
            )
        else:
            comparison.missing.append(want)
    comparison.unexpected.extend(leftover)
