from dataclasses import dataclass, field
from pathlib import Path

from sql_test.engine import (
    Catalog,
    Engine,
    MappingProblem,
    MissingRows,
    Plan,
    Row,
    SourceReason,
)
from sql_test.testing.cases import UncastableCell, read_case
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
    except UncastableCell as error:
        return CaseResult(folder=folder, problem=str(error))
    if case.expected is None:
        return CaseResult(folder=folder, problem="the case has no expected.csv")
    rows = {str(relation): table.rows for relation, table in case.mocks.items()}
    plan = engine.plan(str(case.target), rows)
    if diagnosis := _diagnose_unrunnable_target(plan, engine.catalog):
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


def _diagnose_unrunnable_target(plan: Plan, catalog: Catalog) -> str | None:
    """Name the missing SQL or schema when the target cannot run as a model."""
    reason = plan.source_reasons.get(plan.target)
    if reason is SourceReason.NO_SCHEMA:
        return f"{plan.target} has no schema"
    if reason is SourceReason.NOT_PRODUCED:
        missing = sorted(
            problem.reason
            for problem in catalog.problems
            if isinstance(problem, MappingProblem) and problem.writes == plan.target
        )
        if missing:
            return "; ".join(missing)
    return None
