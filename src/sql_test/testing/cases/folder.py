from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sql_test.engine import Catalog, Column, Relation, Row, Schema

EXPECTED = "expected.csv"


class UncastableCell(Exception):
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


def read_case(folder: Path, catalog: Catalog) -> Case:
    target = catalog.resolve(folder.parent.name)
    mocks = {}
    for path in sorted(folder.glob("*.csv")):
        if path.name != EXPECTED:
            schema = catalog.schema(catalog.resolve(path.stem)) or ()
            mocks[Relation.parse(path.stem)] = _read_table(path, schema)
    expected_path = folder / EXPECTED
    expected = (
        _read_table(expected_path, catalog.schema(target) or ())
        if expected_path.is_file()
        else None
    )
    return Case(target=target, name=folder.name, mocks=mocks, expected=expected)


def write_case(folder: Path, case: Case) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for relation, table in case.mocks.items():
        _write_table(folder / f"{relation}.csv", table)
    if case.expected is not None:
        _write_table(folder / EXPECTED, case.expected)


def _read_table(path: Path, schema: Schema) -> CaseTable:
    columns = {column.name: column for column in schema}
    rows_iter = _notnull_rows(path.read_text())
    header = tuple(_column_name(cell) for cell in next(rows_iter))
    rows = [
        {
            name: _cast(columns.get(name), cell, path, line, name)
            for name, cell in zip(header, cells, strict=True)
        }
        for line, cells in enumerate(rows_iter, start=2)
    ]
    return CaseTable(columns=header, rows=rows)


def _column_name(cell: str | None) -> str:
    if cell is None or cell == "":
        raise UncastableCell("empty column name")
    return cell


def _notnull_rows(text: str) -> Iterator[list[str | None]]:
    """Parse case CSV text: unquoted empty → None, quoted empty → \"\"."""
    # Own parser: csv.QUOTE_NOTNULL leaves unquoted empties as '' on 3.12.
    i = 0
    n = len(text)
    while i < n:
        row: list[str | None] = []
        while True:
            if i < n and text[i] == '"':
                i += 1
                parts: list[str] = []
                while i < n:
                    if text[i] == '"':
                        if i + 1 < n and text[i + 1] == '"':
                            parts.append('"')
                            i += 2
                            continue
                        i += 1
                        break
                    parts.append(text[i])
                    i += 1
                row.append("".join(parts))
            else:
                start = i
                while i < n and text[i] not in ",\r\n":
                    i += 1
                cell = text[start:i]
                row.append(None if cell == "" else cell)
            if i >= n:
                yield row
                return
            if text[i] == ",":
                i += 1
                continue
            if text[i] == "\r":
                i += 1
            if i < n and text[i] == "\n":
                i += 1
            yield row
            break


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
