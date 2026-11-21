import csv
from dataclasses import dataclass
from pathlib import Path

from sql_test.engine.operation import Kind, Operation
from sql_test.engine.relation import Relation


@dataclass(frozen=True)
class MappingProblem:
    file: Path
    reason: str


def read_operations(mapping: Path, sqls: Path) -> list[Operation]:
    with mapping.open(newline="") as file:
        return [
            Operation(
                sql_file=sqls / row["sql_ref"],
                writes=Relation.parse(row["table_ref"]),
                kind=Kind.FULL_LOAD,
            )
            for row in csv.DictReader(file)
        ]


def existing_operations(
    mapping: Path, sqls: Path
) -> tuple[list[Operation], list[MappingProblem]]:
    """The mapping's operations whose SQL file exists, and a problem for each that does not."""
    operations: list[Operation] = []
    problems: list[MappingProblem] = []
    for operation in read_operations(mapping, sqls):
        if operation.sql_file.is_file():
            operations.append(operation)
        else:
            reason = f"{operation.sql_file.relative_to(sqls)} does not exist"
            problems.append(MappingProblem(file=mapping, reason=reason))
    return operations, problems
