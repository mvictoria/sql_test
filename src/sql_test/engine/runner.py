from collections.abc import Callable
from pathlib import Path
from typing import Any

from sql_test.engine.catalog.mapping import read_producers
from sql_test.engine.executor import Executor, Row
from sql_test.engine.planner.order import execution_order
from sql_test.engine.relation import Relation


class Engine:
    def __init__(
        self, sqls: Path, mapping: Path, executor: Callable[[], Executor]
    ) -> None:
        self._sqls = {
            Relation.parse(table): path.read_text()
            for table, path in read_producers(mapping, sqls).items()
        }
        self._executor = executor

    def run(self, table: str, rows: dict[str, list[Row]]) -> list[tuple[Any, ...]]:
        given = {Relation.parse(name): table_rows for name, table_rows in rows.items()}
        known = self._sqls.keys() | given.keys()
        target = Relation.parse(table).resolve(known)
        executor = self._executor()
        try:
            for relation, table_rows in given.items():
                executor.load_rows(str(relation), table_rows)
            for relation in execution_order(target, self._sqls, set(given)):
                executor.create_table_as(str(relation), self._sqls[relation])
            return executor.read_table(str(target))
        finally:
            executor.close()
