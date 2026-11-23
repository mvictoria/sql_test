from __future__ import annotations

import tempfile
import threading
from collections.abc import Mapping, Sequence
from pathlib import Path
from uuid import uuid4

from pyspark.sql import SparkSession

from sql_test.engine.executor import Given, Kind, Operation, Relation, Row

_JDBC_CATALOG = "org.apache.spark.sql.execution.datasources.v2.jdbc.JDBCTableCatalog"
_DERBY_DRIVER = "org.apache.derby.jdbc.EmbeddedDriver"
_SESSION_LOCK = threading.Lock()


class SparkExecutor:
    """Runs share one SparkSession; each uses its own database (or JDBC catalogs).

    `SparkSession.getOrCreate` is process-wide, so all instances share one session
    and one lock around each run (USE and catalog config must stay exclusive). A
    run that names catalogs registers each as a Derby JDBC catalog, then drops
    the run's tables afterwards.
    """

    def __init__(self) -> None:
        self._lock = _SESSION_LOCK
        self._warehouse = Path(tempfile.mkdtemp(prefix="sql_test_spark_wh_"))
        self._spark = (
            SparkSession.builder.master("local[1]")
            .appName("sql_test")
            .config("spark.ui.enabled", "false")
            .config("spark.sql.shuffle.partitions", "1")
            .config("spark.sql.warehouse.dir", str(self._warehouse))
            .getOrCreate()
        )
        self._spark.sparkContext.setLogLevel("ERROR")

    def run(
        self, given: Mapping[Relation, Given], operations: Sequence[Operation]
    ) -> dict[Relation, list[Row]]:
        touched = list(dict.fromkeys([*given, *(op.writes for op in operations)]))
        catalogs = _catalogs(touched)
        with self._lock:
            if catalogs:
                return self._run_with_catalogs(given, operations, touched, catalogs)
            return self._run_in_database(given, operations, touched)

    def _run_in_database(
        self,
        given: Mapping[Relation, Given],
        operations: Sequence[Operation],
        touched: Sequence[Relation],
    ) -> dict[Relation, list[Row]]:
        database = f"run_{uuid4().hex}"
        spark = self._spark
        spark.sql(f"create database {database}")
        spark.sql(f"use {database}")
        try:
            return _run(spark, given, operations, touched)
        finally:
            spark.sql("use default")
            spark.sql(f"drop database if exists {database} cascade")

    def _run_with_catalogs(
        self,
        given: Mapping[Relation, Given],
        operations: Sequence[Operation],
        touched: Sequence[Relation],
        catalogs: Sequence[str],
    ) -> dict[Relation, list[Row]]:
        spark = self._spark
        try:
            for catalog in catalogs:
                self._ensure_catalog(catalog)
            for relation in touched:
                if relation.catalog is None or relation.schema is None:
                    continue
                spark.sql(
                    f"create namespace if not exists {relation.catalog}.{relation.schema}"
                )
            return _run(spark, given, operations, touched)
        finally:
            for relation in touched:
                spark.sql(f"drop table if exists {relation}")

    def _ensure_catalog(self, catalog: str) -> None:
        known = {row.catalog for row in self._spark.sql("show catalogs").collect()}
        if catalog in known:
            return
        root = Path(tempfile.mkdtemp(prefix=f"sql_test_spark_{catalog}_"))
        self._spark.conf.set(f"spark.sql.catalog.{catalog}", _JDBC_CATALOG)
        self._spark.conf.set(
            f"spark.sql.catalog.{catalog}.url",
            f"jdbc:derby:{root / catalog};create=true",
        )
        self._spark.conf.set(f"spark.sql.catalog.{catalog}.driver", _DERBY_DRIVER)


def _catalogs(relations: Sequence[Relation]) -> list[str]:
    return sorted({r.catalog for r in relations if r.catalog is not None})


def _run(
    spark: SparkSession,
    given: Mapping[Relation, Given],
    operations: Sequence[Operation],
    touched: Sequence[Relation],
) -> dict[Relation, list[Row]]:
    for relation, table in given.items():
        _create(spark, relation, table)
    for operation in operations:
        _execute(spark, operation)
    return {relation: _read(spark, relation) for relation in touched}


def _create(spark: SparkSession, relation: Relation, table: Given) -> None:
    _ensure_namespace(spark, relation)
    columns = ", ".join(f"{column.name} {column.type}" for column in table.schema)
    spark.sql(f"create table {relation} ({columns})")
    if not table.rows:
        return
    values = ", ".join(
        "("
        + ", ".join(
            f"cast({_literal(row.get(column.name))} as {column.type})"
            for column in table.schema
        )
        + ")"
        for row in table.rows
    )
    spark.sql(f"insert into {relation} values {values}")


def _execute(spark: SparkSession, operation: Operation) -> None:
    _ensure_namespace(spark, operation.writes)
    if operation.kind is Kind.FULL_LOAD or operation.kind is Kind.MERGE:
        spark.sql(f"drop table if exists {operation.writes}")
        spark.sql(f"create table {operation.writes} as {operation.sql}")
        return
    raise NotImplementedError(operation.kind)


def _read(spark: SparkSession, relation: Relation) -> list[Row]:
    return [
        row.asDict(recursive=True)
        for row in spark.sql(f"select * from {relation}").collect()
    ]


def _ensure_namespace(spark: SparkSession, relation: Relation) -> None:
    if relation.schema is None:
        return
    if relation.catalog is not None:
        spark.sql(
            f"create namespace if not exists {relation.catalog}.{relation.schema}"
        )
        return
    spark.sql(f"create schema if not exists {relation.schema}")


def _literal(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value).replace("'", "''")
    return f"'{text}'"
