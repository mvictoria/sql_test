from typing import Any

import duckdb

type Row = dict[str, Any]


class DuckDBBackend:
    def __init__(self) -> None:
        self._connection = duckdb.connect()

    def load_rows(self, table: str, rows: list[Row]) -> None:
        columns = list(rows[0])
        placeholders = "(" + ", ".join(["?"] * len(columns)) + ")"
        values = ", ".join(placeholders for _ in rows)
        self._connection.execute(
            f"create table {table} as select * from (values {values}) t({', '.join(columns)})",
            [row[column] for row in rows for column in columns],
        )

    def create_table_as(self, table: str, sql: str) -> None:
        self._connection.execute(f"create table {table} as {sql}")

    def read_table(self, table: str) -> list[tuple[Any, ...]]:
        return self._connection.execute(f"select * from {table}").fetchall()

    def close(self) -> None:
        self._connection.close()
