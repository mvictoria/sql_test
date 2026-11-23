import csv
from dataclasses import dataclass
from pathlib import Path

from sql_test.engine.operation import Kind, Operation
from sql_test.engine.relation import Relation

REQUIRED_COLUMNS = ("table_ref", "sql_ref")


class MappingError(Exception):
    pass


@dataclass(frozen=True)
class MappingProblem:
    file: Path
    reason: str
    writes: Relation


def read_operations(mapping: Path, sqls: Path) -> list[Operation]:
    with mapping.open(newline="") as file:
        reader = csv.DictReader(file)
        headers = set(reader.fieldnames or ())
        missing = [name for name in REQUIRED_COLUMNS if name not in headers]
        if missing:
            expected = ", ".join(REQUIRED_COLUMNS)
            raise MappingError(
                f"{mapping} is missing columns {', '.join(missing)}; "
                f"expected columns {expected}"
            )
        return [
            Operation(
                sql_file=sqls / row["sql_ref"],
                writes=Relation.parse(row["table_ref"]),
                kind=Kind.from_load_type(row.get("load_type")),
            )
            for row in reader
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
            problems.append(
                MappingProblem(file=mapping, reason=reason, writes=operation.writes)
            )
    return operations, problems
