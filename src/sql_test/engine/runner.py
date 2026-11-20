from collections.abc import Callable
from pathlib import Path
from typing import Any

from sql_test.engine.catalog.mapping import read_producers
from sql_test.engine.executor import Executor, Row
from sql_test.engine.planner.order import execution_order


class Engine:
    def __init__(
        self, sqls: Path, mapping: Path, executor: Callable[[], Executor]
    ) -> None:
        self._sqls = {
            table: path.read_text()
            for table, path in read_producers(mapping, sqls).items()
        }
        self._executor = executor

    def run(self, table: str, rows: dict[str, list[Row]]) -> list[tuple[Any, ...]]:
        executor = self._executor()
        try:
            for name, table_rows in rows.items():
                executor.load_rows(name, table_rows)
            for name in execution_order(table, self._sqls, set(rows)):
                executor.create_table_as(name, self._sqls[name])
            return executor.read_table(table)
        finally:
            executor.close()
