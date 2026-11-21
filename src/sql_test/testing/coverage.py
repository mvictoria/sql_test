from collections.abc import Iterable

from sql_test.engine import Catalog, State, plan_run
from sql_test.testing.cases import CaseSummary


def case_counts(tables: Iterable[str], cases: Iterable[CaseSummary]) -> dict[str, int]:
    """How many discovered cases target each table, including zero."""
    counts = {name: 0 for name in tables}
    for case in cases:
        counts[case.target] = counts.get(case.target, 0) + 1
    return counts


def pipeline_counts(
    tables: Iterable[str],
    cases: Iterable[CaseSummary],
    catalog: Catalog,
) -> dict[str, int]:
    """How many other cases execute each table's SQL (lineage + mocks; no run)."""
    counts = {name: 0 for name in tables}
    for case in cases:
        target = catalog.resolve(case.target)
        given = {catalog.resolve(name): 1 for name in case.mocks}
        plan = plan_run(target, catalog, given)
        for relation, state in plan.states.items():
            if state is not State.EXECUTED:
                continue
            name = str(relation)
            if name == case.target or name not in counts:
                continue
            counts[name] += 1
    return counts


def pipeline_cases(
    table: str,
    cases: Iterable[CaseSummary],
    catalog: Catalog,
) -> list[CaseSummary]:
    """Cases that execute `table`'s SQL without targeting it."""
    relation = catalog.resolve(table)
    found: list[CaseSummary] = []
    for case in cases:
        if case.target == str(relation) or case.target == table:
            continue
        target = catalog.resolve(case.target)
        given = {catalog.resolve(name): 1 for name in case.mocks}
        plan = plan_run(target, catalog, given)
        if plan.states.get(relation) is State.EXECUTED:
            found.append(case)
    return found
