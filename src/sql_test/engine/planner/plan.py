from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from graphlib import TopologicalSorter

from sql_test.engine.catalog import Catalog
from sql_test.engine.catalog.mapping import MappingProblem
from sql_test.engine.lineage.graph import SourceReason, upstream_lineage
from sql_test.engine.operation import Kind, Operation
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
    incremental: set[Relation]
    operations: list[Operation]

    @property
    def executed(self) -> frozenset[Relation]:
        return frozenset(
            relation
            for relation, state in self.states.items()
            if state is State.EXECUTED
        )

    def blocker(self, catalog: Catalog) -> str | None:
        """Why `target` cannot run as a model, if it cannot."""
        reason = self.source_reasons.get(self.target)
        if reason is SourceReason.NO_SCHEMA:
            return f"{self.target} has no schema"
        if reason is SourceReason.NOT_PRODUCED:
            missing = sorted(
                problem.reason
                for problem in catalog.problems
                if isinstance(problem, MappingProblem) and problem.writes == self.target
            )
            if missing:
                return "; ".join(missing)
        return None


def plan_run(
    target: Relation,
    catalog: Catalog,
    given: Mapping[Relation, int],
    *,
    with_pruned: bool = False,
) -> Plan:
    """Plan building `target`; `given` maps each given relation to its row count.

    The walk stops at given relations unless `with_pruned` asks for what lies past them.
    Given rows for an incremental model are its target before: the model still executes.
    """
    incremental_models = _incremental_models(catalog)
    boundaries = () if with_pruned else set(given) - incremental_models
    lineage = upstream_lineage(target, catalog, boundaries)
    projection = lineage.projection()
    states: dict[Relation, State] = {}
    built_from: dict[Relation, set[Relation]] = {}
    pending = [target]
    while pending:
        relation = pending.pop()
        if relation in states:
            continue
        if relation in given and relation not in incremental_models:
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
    incremental = {
        relation
        for relation in lineage.incremental
        if states.get(relation) is State.EXECUTED
    }
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
            relation
            for relation in given
            if states.get(relation) is not State.GIVEN and relation not in incremental
        },
        incremental=incremental,
    )


def _incremental_models(catalog: Catalog) -> set[Relation]:
    return {
        operation.writes
        for operation in catalog.operations
        if operation.kind is not Kind.FULL_LOAD
    }
