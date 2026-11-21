from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from graphlib import TopologicalSorter

from sql_test.engine.catalog import Catalog
from sql_test.engine.lineage.graph import SourceReason, upstream_lineage
from sql_test.engine.operation import Operation
from sql_test.engine.relation import Relation


class State(StrEnum):
    GIVEN = "given"
    EXECUTED = "executed"
    PRUNED = "pruned"
    SOURCE = "source"


class MissingRows(Exception):
    pass


@dataclass(frozen=True)
class Plan:
    target: Relation
    states: dict[Relation, State]
    built_from: dict[Relation, set[Relation]]
    source_reasons: dict[Relation, SourceReason]
    needs_rows: set[Relation]
    unused: set[Relation]
    operations: list[Operation]


def plan_run(target: Relation, catalog: Catalog, given: Mapping[Relation, int]) -> Plan:
    """Plan building `target`; `given` maps each given relation to its row count."""
    lineage = upstream_lineage(target, catalog)
    projection = lineage.projection()
    states: dict[Relation, State] = {}
    built_from: dict[Relation, set[Relation]] = {}
    pending = [target]
    while pending:
        relation = pending.pop()
        if relation in states:
            continue
        if relation in given:
            states[relation] = State.GIVEN
        elif relation in lineage.models:
            states[relation] = State.EXECUTED
            built_from[relation] = projection[relation]
            pending.extend(built_from[relation])
        else:
            states[relation] = State.SOURCE
    for relation in lineage.models | lineage.sources:
        states.setdefault(relation, State.PRUNED)
    operations = [
        operation
        for relation in TopologicalSorter(built_from).static_order()
        if relation in built_from
        for operation in lineage.producers[relation]
    ]
    needs_rows = {
        relation
        for relation, state in states.items()
        if state is State.SOURCE or (state is State.GIVEN and not given[relation])
    }
    return Plan(
        target=target,
        states=states,
        built_from=projection,
        source_reasons=lineage.source_reasons,
        operations=operations,
        needs_rows=needs_rows,
        unused={
            relation for relation in given if states.get(relation) is not State.GIVEN
        },
    )
