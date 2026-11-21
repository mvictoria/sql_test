from collections.abc import Callable
from dataclasses import dataclass

from sql_test.engine.catalog import Catalog
from sql_test.engine.executor import Executor, Row
from sql_test.engine.lineage.references import ends_in_order_by
from sql_test.engine.planner.plan import Plan, plan_run
from sql_test.engine.relation import Relation
from sql_test.engine.schema import Column, Schema


@dataclass(frozen=True)
class RunResult:
    rows: list[Row]
    counts: dict[Relation, int]
    ordered: bool


class Engine:
    def __init__(self, catalog: Catalog, executor: Callable[[], Executor]) -> None:
        self._catalog = catalog
        self._executor = executor

    @property
    def catalog(self) -> Catalog:
        return self._catalog

    def plan(self, table: str, rows: dict[str, list[Row]]) -> Plan:
        given = {
            Relation.parse(name): len(table_rows) for name, table_rows in rows.items()
        }
        known = self._catalog.relations().keys() | given.keys()
        return plan_run(Relation.parse(table).resolve(known), self._catalog, given)

    def run(self, table: str, rows: dict[str, list[Row]]) -> RunResult:
        plan = self.plan(table, rows)
        plan.check_rows()
        executor = self._executor()
        executor.setup()
        try:
            known = self._catalog.relations().keys()
            counts: dict[Relation, int] = {}
            for name, table_rows in rows.items():
                relation = Relation.parse(name).resolve(known)
                schema = self._catalog.schemas.get(relation) or _schema_from_rows(
                    table_rows
                )
                executor.create_relation(relation, schema, table_rows)
                counts[relation] = len(table_rows)
            for operation in plan.operations:
                executor.execute(operation)
                counts[operation.writes] = len(executor.read_rows(operation.writes))
            target = plan.lineage.target
            result = executor.read_rows(target)
            counts[target] = len(result)
        finally:
            executor.teardown()
        return RunResult(
            rows=result,
            counts=counts,
            ordered=any(
                ends_in_order_by(operation.sql)
                for operation in plan.operations
                if operation.writes == target
            ),
        )


def _schema_from_rows(rows: list[Row]) -> Schema:
    return tuple(Column(name=name, type="VARCHAR") for name in rows[0])
