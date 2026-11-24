from typing import TYPE_CHECKING

from sql_test.executors.duckdb import DuckDBExecutor

if TYPE_CHECKING:
    from sql_test.executors.spark import SparkExecutor as SparkExecutor

__all__ = ["DuckDBExecutor", "SparkExecutor"]


def __getattr__(name: str):
    if name == "SparkExecutor":
        from sql_test.executors.spark import SparkExecutor

        return SparkExecutor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
