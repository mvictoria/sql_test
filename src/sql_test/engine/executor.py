from typing import Any, Protocol

from sql_test.engine.operation import Kind, Operation
from sql_test.engine.relation import Relation
from sql_test.engine.schema import Schema

__all__ = ["Executor", "Kind", "Operation", "Relation", "Row", "Schema"]

type Row = dict[str, Any]


class Executor(Protocol):
    def setup(self) -> None: ...

    def create_relation(
        self, relation: Relation, schema: Schema, rows: list[Row]
    ) -> None: ...

    def execute(self, operation: Operation) -> None: ...

    def read_rows(self, relation: Relation) -> list[Row]: ...

    def teardown(self) -> None: ...
