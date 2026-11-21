from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from sql_test.engine.operation import Kind, Operation
from sql_test.engine.relation import Relation
from sql_test.engine.schema import Schema

__all__ = ["Executor", "Given", "Kind", "Operation", "Relation", "Row", "Schema"]

type Row = dict[str, Any]


@dataclass(frozen=True)
class Given:
    schema: Schema
    rows: list[Row]


class Executor(Protocol):
    def run(
        self, given: Mapping[Relation, Given], operations: Sequence[Operation]
    ) -> dict[Relation, list[Row]]:
        """Load `given` and execute `operations` in order, sharing nothing with
        other runs; return the rows of every given and written relation."""
        ...
