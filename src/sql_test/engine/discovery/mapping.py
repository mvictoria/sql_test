import csv
from pathlib import Path


def read_producers(mapping: Path, sqls: Path) -> dict[str, Path]:
    with mapping.open(newline="") as file:
        return {row["table_ref"]: sqls / row["sql_ref"] for row in csv.DictReader(file)}
