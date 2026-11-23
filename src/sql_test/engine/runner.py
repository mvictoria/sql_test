from dataclasses import dataclass

from sql_test.engine.catalog import Catalog
from sql_test.engine.executor import Executor, Given, Row
from sql_test.engine.lineage.references import ends_in_order_by
from sql_test.engine.planner.plan import Plan, plan_run
from sql_test.engine.relation import Relation
from sql_test.engine.schema import Column, Schema


class MissingRows(Exception):
    pass


@dataclass(frozen=True)
class RunResult:
    rows: list[Row]
    counts: dict[Relation, int]
    ordered: bool


class Engine:
    def __init__(self, catalog: Catalog, executor: Executor | None = None) -> None:
        self._catalog = catalog
        self._executor = executor

    @property
    def catalog(self) -> Catalog:
        return self._catalog

    def plan(
        self, table: str, rows: dict[str, list[Row]], *, with_pruned: bool = False
    ) -> Plan:
        given = {
            self._catalog.resolve(name): len(table_rows)
            for name, table_rows in rows.items()
        }
        known = self._catalog.relations() | given.keys()
        return plan_run(
            Relation.parse(table).resolve(known),
            self._catalog,
            given,
            with_pruned=with_pruned,
        )

    def execute(self, plan: Plan, rows: dict[str, list[Row]]) -> RunResult:
        if self._executor is None:
            raise RuntimeError("engine has no executor")
        if plan.needs_rows:
            names = ", ".join(sorted(map(str, plan.needs_rows)))
            raise MissingRows(f"These relations still need rows: {names}")
        given: dict[Relation, Given] = {}
        for name, table_rows in rows.items():
            relation = self._catalog.resolve(name)
            schema = self._catalog.schema(relation) or _schema_from_rows(table_rows)
            given[relation] = Given(schema=schema, rows=table_rows)
        written = self._executor.run(given, plan.operations)
        target = plan.target
        return RunResult(
            rows=written[target],
            counts={
                relation: len(table_rows) for relation, table_rows in written.items()
            },
            ordered=any(
                ends_in_order_by(operation.sql)
                for operation in plan.operations
                if operation.writes == target
            ),
        )

    def run(self, table: str, rows: dict[str, list[Row]]) -> RunResult:
        return self.execute(self.plan(table, rows), rows)


def _schema_from_rows(rows: list[Row]) -> Schema:
    return tuple(Column(name=name, type="VARCHAR") for name in rows[0])
