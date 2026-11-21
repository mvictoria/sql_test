from typing import Any, Protocol

from sql_test.engine.operation import Operation
from sql_test.engine.relation import Relation
from sql_test.engine.schema import Schema

type Row = dict[str, Any]


class Executor(Protocol):
    def setup(self) -> None: ...

    def create_relation(
        self, relation: Relation, schema: Schema, rows: list[Row]
    ) -> None: ...

    def execute(self, operation: Operation) -> None: ...

    def read_relation(self, relation: Relation) -> list[tuple[Any, ...]]: ...

    def teardown(self) -> None: ...
