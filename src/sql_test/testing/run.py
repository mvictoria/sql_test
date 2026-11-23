from dataclasses import dataclass, field, replace
from pathlib import Path

from sql_test.engine import Engine, Kind, MissingRows, Row
from sql_test.testing.cases import Case, UncastableCell, UnknownColumns, read_case
from sql_test.testing.comparison import Comparison, compare


@dataclass(frozen=True)
class CaseResult:
    folder: Path
    actual: list[Row] = field(default_factory=list)
    comparison: Comparison | None = None
    problem: str | None = None

    @property
    def passed(self) -> bool:
        return (
            self.problem is None
            and self.comparison is not None
            and self.comparison.passed
        )

    def report(self) -> str:
        lines = [f"{self.folder.parent.name}/{self.folder.name}"]
        if self.problem:
            lines.append(self.problem)
        if self.comparison is not None:
            comparison = self.comparison
            if comparison.missing_columns:
                lines.append(f"columns not in output: {comparison.missing_columns}")
            lines += [
                f"changed {c.differing_columns}: {c.expected} -> {c.actual}"
                for c in comparison.changed
            ]
            lines += [f"missing: {row}" for row in comparison.missing]
            lines += [f"unexpected: {row}" for row in comparison.unexpected]
        return "\n".join(lines)


def run_case(folder: Path, engine: Engine) -> CaseResult:
    try:
        case = read_case(folder, engine.catalog)
    except (UncastableCell, UnknownColumns) as error:
        return CaseResult(folder=folder, problem=str(error))
    return run_loaded_case(folder, engine, case)


def run_loaded_case(folder: Path, engine: Engine, case: Case) -> CaseResult:
    if case.expected is None:
        return CaseResult(folder=folder, problem="the case has no expected.csv")
    if case.incremental:
        return _run_cdc_case(folder, engine, case)
    return _run_full_load_case(folder, engine, case)


def _run_full_load_case(folder: Path, engine: Engine, case: Case) -> CaseResult:
    assert case.expected is not None
    rows = {str(relation): table.rows for relation, table in case.mocks.items()}
    plan = engine.plan(str(case.target), rows)
    if diagnosis := plan.blocker(engine.catalog):
        return CaseResult(folder=folder, problem=diagnosis)
    if plan.unused:
        names = ", ".join(sorted(map(str, plan.unused)))
        return CaseResult(folder=folder, problem=f"mocks the run never reads: {names}")
    try:
        result = engine.execute(plan, rows)
    except MissingRows as error:
        return CaseResult(folder=folder, problem=str(error))
    return CaseResult(
        folder=folder,
        actual=result.rows,
        comparison=compare(case.expected, result.rows, ordered=result.ordered),
    )


def _run_cdc_case(folder: Path, engine: Engine, case: Case) -> CaseResult:
    """History → historical producers → apply deltas → incremental producers."""
    history = {str(relation): table.rows for relation, table in case.mocks.items()}
    plan = engine.plan(str(case.target), history)
    if diagnosis := plan.blocker(engine.catalog):
        return CaseResult(folder=folder, problem=diagnosis)
    historic = replace(
        plan,
        operations=[op for op in plan.operations if op.kind is Kind.FULL_LOAD],
        incremental=set(),
    )
    try:
        before_result = engine.execute(historic, history)
    except MissingRows as error:
        return CaseResult(folder=folder, problem=str(error))
    tables = dict(before_result.tables or {})
    for relation, table in case.mocks.items():
        resolved = engine.catalog.resolve(str(relation))
        tables.setdefault(resolved, list(table.rows))
    for relation, table in case.deltas.items():
        resolved = engine.catalog.resolve(str(relation))
        tables[resolved] = [*tables.get(resolved, []), *table.rows]
    cdc_rows = {str(relation): rows for relation, rows in tables.items()}
    cdc = replace(
        plan,
        operations=[op for op in plan.operations if op.kind is not Kind.FULL_LOAD],
        incremental={
            op.writes for op in plan.operations if op.kind is not Kind.FULL_LOAD
        },
        needs_rows=set(),
        unused=set(),
    )
    if not cdc.operations:
        return CaseResult(
            folder=folder,
            problem=f"{case.target} has no incremental producer for the CDC run",
        )
    try:
        result = engine.execute(cdc, cdc_rows)
    except MissingRows as error:
        return CaseResult(folder=folder, problem=str(error))
    assert case.expected is not None
    return CaseResult(
        folder=folder,
        actual=result.rows,
        comparison=compare(case.expected, result.rows, ordered=result.ordered),
    )
