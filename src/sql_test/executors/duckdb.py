from typing import Any

import duckdb

from sql_test.engine.executor import Row
from sql_test.engine.operation import Kind, Operation
from sql_test.engine.relation import Relation
from sql_test.engine.schema import Schema


class DuckDBExecutor:
    def __init__(self) -> None:
        self._connection: duckdb.DuckDBPyConnection | None = None

    def setup(self) -> None:
        self._connection = duckdb.connect()

    def create_relation(
        self, relation: Relation, schema: Schema, rows: list[Row]
    ) -> None:
        connection = self._connection
        assert connection is not None
        self._ensure_namespace(relation)
        columns = ", ".join(f"{column.name} {column.type}" for column in schema)
        connection.execute(f"create table {relation} ({columns})")
        if not rows:
            return
        placeholders = ", ".join("?" for _ in schema)
        connection.executemany(
            f"insert into {relation} values ({placeholders})",
            [[row[column.name] for column in schema] for row in rows],
        )

    def execute(self, operation: Operation) -> None:
        connection = self._connection
        assert connection is not None
        if operation.kind is Kind.FULL_LOAD:
            self._ensure_namespace(operation.writes)
            connection.execute(f"create table {operation.writes} as {operation.sql}")
            return
        raise NotImplementedError(operation.kind)

    def read_relation(self, relation: Relation) -> list[tuple[Any, ...]]:
        connection = self._connection
        assert connection is not None
        return connection.execute(f"select * from {relation}").fetchall()

    def teardown(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def _ensure_namespace(self, relation: Relation) -> None:
        connection = self._connection
        assert connection is not None
        if relation.schema is not None:
            connection.execute(f'create schema if not exists "{relation.schema}"')
