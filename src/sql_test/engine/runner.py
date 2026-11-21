from collections.abc import Callable
from typing import Any

from sql_test.engine.catalog import Catalog
from sql_test.engine.executor import Executor, Row
from sql_test.engine.planner.plan import Plan, plan_run
from sql_test.engine.relation import Relation


class Engine:
    def __init__(self, catalog: Catalog, executor: Callable[[], Executor]) -> None:
        self._catalog = catalog
        self._executor = executor

    def plan(self, table: str, rows: dict[str, list[Row]]) -> Plan:
        given = {
            Relation.parse(name): len(table_rows) for name, table_rows in rows.items()
        }
        known = self._catalog.relations().keys() | given.keys()
        return plan_run(Relation.parse(table).resolve(known), self._catalog, given)

    def run(self, table: str, rows: dict[str, list[Row]]) -> list[tuple[Any, ...]]:
        plan = self.plan(table, rows)
        plan.check_rows()
        executor = self._executor()
        try:
            for name, table_rows in rows.items():
                executor.load_rows(str(Relation.parse(name)), table_rows)
            for operation in plan.operations:
                executor.create_table_as(str(operation.writes), operation.sql)
            return executor.read_table(str(plan.lineage.target))
        finally:
            executor.close()
