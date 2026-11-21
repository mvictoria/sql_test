from collections import defaultdict
from graphlib import TopologicalSorter

from sql_test.engine.lineage.references import tables_read
from sql_test.engine.operation import Operation
from sql_test.engine.relation import Relation


def execution_order(
    table: Relation, operations: list[Operation], given: set[Relation]
) -> list[Operation]:
    producers: dict[Relation, list[Operation]] = defaultdict(list)
    for operation in operations:
        producers[operation.writes].append(operation)
    known = producers.keys() | given
    upstream: dict[Relation, set[Relation]] = {}
    pending = [table]
    while pending:
        current = pending.pop()
        if current in upstream or current in given or current not in producers:
            continue
        upstream[current] = {
            reference.resolve(known)
            for operation in producers[current]
            for reference in tables_read(operation.sql)
        }
        pending.extend(upstream[current])
    return [
        operation
        for relation in TopologicalSorter(upstream).static_order()
        if relation in upstream
        for operation in producers[relation]
    ]
