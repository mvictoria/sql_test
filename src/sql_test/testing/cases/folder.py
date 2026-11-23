import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sql_test.engine import Catalog, Column, Relation, Row, Schema

EXPECTED = "expected.csv"
DELTA = "delta"


class UncastableCell(Exception):
    pass


class UnknownColumns(Exception):
    pass


@dataclass(frozen=True)
class CaseTable:
    columns: tuple[str, ...]
    rows: list[Row]


@dataclass(frozen=True)
class Case:
    target: Relation
    name: str
    mocks: dict[Relation, CaseTable]
    expected: CaseTable | None
    deltas: dict[Relation, CaseTable] = field(default_factory=dict)

    @property
    def incremental(self) -> bool:
        return bool(self.deltas)


def read_case(folder: Path, catalog: Catalog) -> Case:
    target = catalog.resolve(folder.parent.name)
    mocks = {}
    for path in sorted(folder.glob("*.csv")):
        if path.name != EXPECTED:
            relation = Relation.parse(path.stem)
            schema = catalog.schema(catalog.resolve(path.stem)) or ()
            mocks[relation] = _read_table(path, schema, relation)
    deltas = {}
    delta_folder = folder / DELTA
    if delta_folder.is_dir():
        for path in sorted(delta_folder.glob("*.csv")):
            relation = Relation.parse(path.stem)
            schema = catalog.schema(catalog.resolve(path.stem)) or ()
            deltas[relation] = _read_table(path, schema, relation)
    expected_path = folder / EXPECTED
    expected = (
        _read_table(expected_path, catalog.schema(target) or (), target)
        if expected_path.is_file()
        else None
    )
    return Case(
        target=target,
        name=folder.name,
        mocks=mocks,
        expected=expected,
        deltas=deltas,
    )


def write_case(folder: Path, case: Case) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for relation, table in case.mocks.items():
        _write_table(folder / f"{relation}.csv", table)
    if case.deltas:
        delta_folder = folder / DELTA
        delta_folder.mkdir(parents=True, exist_ok=True)
        for relation, table in case.deltas.items():
            _write_table(delta_folder / f"{relation}.csv", table)
    if case.expected is not None:
        _write_table(folder / EXPECTED, case.expected)


def _read_table(path: Path, schema: Schema, relation: Relation) -> CaseTable:
    columns = {column.name: column for column in schema}
    with path.open(newline="") as file:
        reader = csv.reader(file, quoting=csv.QUOTE_NOTNULL)
        header = tuple(next(reader))
        if columns:
            unknown = tuple(name for name in header if name not in columns)
            if unknown:
                names = ", ".join(unknown)
                raise UnknownColumns(f"unknown columns on {relation}: {names}")
        rows = [
            {
                name: _cast(columns.get(name), cell, path, line, name)
                for name, cell in zip(header, cells, strict=True)
            }
            for line, cells in enumerate(reader, start=2)
        ]
    return CaseTable(columns=header, rows=rows)


def _cast(
    column: Column | None, cell: str | None, path: Path, line: int, name: str
) -> Any:
    if column is None:
        return cell
    try:
        return column.cast(cell)
    except ValueError as error:
        raise UncastableCell(
            f"{path.name} line {line} {name}: {cell!r} is not {column.type}"
        ) from error


def _write_table(path: Path, table: CaseTable) -> None:
    lines = [",".join(map(_field, table.columns))]
    lines += [
        ",".join(_field(_text(row[name])) for name in table.columns)
        for row in table.rows
    ]
    path.write_text("".join(f"{line}\n" for line in lines))


def _text(value: Any) -> str | None:
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _field(text: str | None) -> str:
    if text is None:
        return ""
    if text == "" or any(char in text for char in ',"\r\n'):
        return '"' + text.replace('"', '""') + '"'
    return text
