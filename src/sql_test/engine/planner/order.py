from graphlib import TopologicalSorter

from sql_test.engine.lineage.references import tables_read
from sql_test.engine.relation import Relation


def execution_order(
    table: Relation, sqls: dict[Relation, str], given: set[Relation]
) -> list[Relation]:
    known = sqls.keys() | given
    upstream: dict[Relation, set[Relation]] = {}
    pending = [table]
    while pending:
        current = pending.pop()
        if current in upstream or current in given or current not in sqls:
            continue
        upstream[current] = {
            reference.resolve(known) for reference in tables_read(sqls[current])
        }
        pending.extend(upstream[current])
    return [
        name for name in TopologicalSorter(upstream).static_order() if name in upstream
    ]
