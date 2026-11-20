from pathlib import Path
from typing import Any

from sql_test.engine.discovery.mapping import read_producers
from sql_test.engine.execution.duckdb import DuckDBBackend, Row


class Engine:
    def __init__(self, sqls: Path, mapping: Path) -> None:
        self._producers = read_producers(mapping, sqls)

    def run(self, table: str, rows: dict[str, list[Row]]) -> list[tuple[Any, ...]]:
        backend = DuckDBBackend()
        try:
            for name, table_rows in rows.items():
                backend.load_rows(name, table_rows)
            backend.create_table_as(table, self._producers[table].read_text())
            return backend.read_table(table)
        finally:
            backend.close()
