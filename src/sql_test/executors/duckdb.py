from collections.abc import Mapping, Sequence
from uuid import uuid4

import duckdb

from sql_test.engine.executor import Given, Kind, Operation, Relation, Row

_RESERVED_CATALOGS = frozenset({"memory", "system", "temp"})


class DuckDBExecutor:
    """Runs share one DuckDB instance; each attaches and drops its own database.

    A run naming catalogs gets a throwaway instance instead, because attached
    database names are global to an instance.
    """

    def __init__(self) -> None:
        self._instance = duckdb.connect()

    def run(
        self, given: Mapping[Relation, Given], operations: Sequence[Operation]
    ) -> dict[Relation, list[Row]]:
        touched = list(dict.fromkeys([*given, *(op.writes for op in operations)]))
        catalogs = _catalogs(touched)
        if catalogs:
            with duckdb.connect() as connection:
                for catalog in catalogs:
                    connection.execute(f"attach ':memory:' as \"{catalog}\"")
                return _run(connection, given, operations, touched)
        database = f"run_{uuid4().hex}"
        with self._instance.cursor() as connection:
            connection.execute(f"attach ':memory:' as {database}")
            try:
                connection.execute(f"use {database}")
                return _run(connection, given, operations, touched)
            finally:
                connection.execute("use memory")
                connection.execute(f"detach {database}")


def _catalogs(relations: Sequence[Relation]) -> list[str]:
    catalogs = sorted({r.catalog for r in relations if r.catalog is not None})
    for relation in relations:
        if (
            relation.catalog is not None
            and relation.catalog.lower() in _RESERVED_CATALOGS
        ):
            raise ValueError(
                f"{relation} uses DuckDB's own database {relation.catalog!r} as its catalog"
            )
    return catalogs


def _run(
    connection: duckdb.DuckDBPyConnection,
    given: Mapping[Relation, Given],
    operations: Sequence[Operation],
    touched: Sequence[Relation],
) -> dict[Relation, list[Row]]:
    for relation, table in given.items():
        _create(connection, relation, table)
    for operation in operations:
        _execute(connection, operation)
    return {relation: _read(connection, relation) for relation in touched}


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
        prefix = f'"{relation.catalog}".' if relation.catalog else ""
        connection.execute(f'create schema if not exists {prefix}"{relation.schema}"')
