from collections.abc import Mapping, Sequence
from uuid import uuid4

import duckdb

from sql_test.engine.executor import Given, Kind, Operation, Relation, Row


class DuckDBExecutor:
    """Runs share one DuckDB instance; each attaches and drops its own database."""

    def __init__(self) -> None:
        self._instance = duckdb.connect()

    def run(
        self, given: Mapping[Relation, Given], operations: Sequence[Operation]
    ) -> dict[Relation, list[Row]]:
        database = f"run_{uuid4().hex}"
        with self._instance.cursor() as connection:
            connection.execute(f"attach ':memory:' as {database}")
            try:
                connection.execute(f"use {database}")
                for relation, table in given.items():
                    _create(connection, relation, table)
                for operation in operations:
                    _execute(connection, operation)
                touched = dict.fromkeys([*given, *(op.writes for op in operations)])
                return {relation: _read(connection, relation) for relation in touched}
            finally:
                connection.execute("use memory")
                connection.execute(f"detach {database}")


def _create(
    connection: duckdb.DuckDBPyConnection, relation: Relation, table: Given
) -> None:
    _ensure_namespace(connection, relation)
    columns = ", ".join(f"{column.name} {column.type}" for column in table.schema)
    connection.execute(f"create table {relation} ({columns})")
    if table.rows:
        placeholders = ", ".join("?" for _ in table.schema)
        connection.executemany(
            f"insert into {relation} values ({placeholders})",
            [[row.get(column.name) for column in table.schema] for row in table.rows],
        )


def _execute(connection: duckdb.DuckDBPyConnection, operation: Operation) -> None:
    if operation.kind is not Kind.FULL_LOAD:
        raise NotImplementedError(operation.kind)
    _ensure_namespace(connection, operation.writes)
    connection.execute(f"create table {operation.writes} as {operation.sql}")


def _read(connection: duckdb.DuckDBPyConnection, relation: Relation) -> list[Row]:
    cursor = connection.execute(f"select * from {relation}")
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, values, strict=True)) for values in cursor.fetchall()]


def _ensure_namespace(
    connection: duckdb.DuckDBPyConnection, relation: Relation
) -> None:
    if relation.schema is not None:
        connection.execute(f'create schema if not exists "{relation.schema}"')
