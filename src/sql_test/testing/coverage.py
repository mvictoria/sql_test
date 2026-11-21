from collections.abc import Iterable

from sql_test.engine import Catalog, Relation, State, plan_run
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
    known = catalog.relations()
    for case in cases:
        target = Relation.parse(case.target).resolve(known)
        given = {Relation.parse(name).resolve(known): 1 for name in case.mocks}
        plan = plan_run(target, catalog, given)
        for relation, state in plan.states.items():
            if state is not State.EXECUTED:
                continue
            name = str(relation)
            if name == case.target or name not in counts:
                continue
            counts[name] += 1
    return counts
