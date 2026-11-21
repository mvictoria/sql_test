from collections.abc import Callable
from typing import Any

from sql_test.engine.catalog import Catalog
from sql_test.engine.executor import Executor, Row
from sql_test.engine.planner.order import execution_order
from sql_test.engine.relation import Relation


class Engine:
    def __init__(self, catalog: Catalog, executor: Callable[[], Executor]) -> None:
        self._catalog = catalog
        self._executor = executor

    def run(self, table: str, rows: dict[str, list[Row]]) -> list[tuple[Any, ...]]:
        given = {Relation.parse(name): table_rows for name, table_rows in rows.items()}
        known = self._catalog.relations().keys() | given.keys()
        target = Relation.parse(table).resolve(known)
        executor = self._executor()
        try:
            for relation, table_rows in given.items():
                executor.load_rows(str(relation), table_rows)
            for operation in execution_order(target, self._catalog, set(given)):
                executor.create_table_as(str(operation.writes), operation.sql)
            return executor.read_table(str(target))
        finally:
            executor.close()
