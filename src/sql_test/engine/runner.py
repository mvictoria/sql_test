from pathlib import Path
from typing import Any

from sql_test.engine.discovery.mapping import read_producers
from sql_test.engine.execution.duckdb import DuckDBBackend, Row
from sql_test.engine.lineage.order import execution_order


class Engine:
    def __init__(self, sqls: Path, mapping: Path) -> None:
        self._sqls = {
            table: path.read_text()
            for table, path in read_producers(mapping, sqls).items()
        }

    def run(self, table: str, rows: dict[str, list[Row]]) -> list[tuple[Any, ...]]:
        backend = DuckDBBackend()
        try:
            for name, table_rows in rows.items():
                backend.load_rows(name, table_rows)
            for name in execution_order(table, self._sqls, set(rows)):
                backend.create_table_as(name, self._sqls[name])
            return backend.read_table(table)
        finally:
            backend.close()
