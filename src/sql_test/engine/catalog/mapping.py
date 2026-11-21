import csv
from pathlib import Path

from sql_test.engine.operation import Kind, Operation
from sql_test.engine.relation import Relation


def read_operations(mapping: Path, sqls: Path) -> list[Operation]:
    with mapping.open(newline="") as file:
        return [
            Operation(
                sql_file=sqls / row["sql_ref"],
                writes=Relation.parse(row["table_ref"]),
                kind=Kind.from_load_type(row.get("load_type")),
            )
            for row in csv.DictReader(file)
        ]
