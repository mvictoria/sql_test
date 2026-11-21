from collections.abc import Iterator
from pathlib import Path

import sqlglot
from sqlglot import exp
from sqlglot.dialects.dialect import Dialect
from sqlglot.errors import SqlglotError
from sqlglot.tokens import TokenType

from sql_test.engine.relation import Relation
from sql_test.engine.schema import Column, DiscoveredSchemas, SchemaProblem


def read_ddl_schemas(folder: Path, dialect: str | None = None) -> DiscoveredSchemas:
    discovered = DiscoveredSchemas()
    for path in sorted(folder.rglob("*.sql")):
        try:
            statements = list(_statements(path.read_text(), dialect))
        except SqlglotError as error:
            discovered.problems.append(SchemaProblem(path, str(error)))
            continue
        for text in statements:
            try:
                statement = sqlglot.parse_one(text, read=dialect)
            except SqlglotError as error:
                discovered.problems.append(SchemaProblem(path, str(error)))
                continue
            if not isinstance(statement, exp.Create):
                continue
            schema = statement.this
            if not isinstance(schema, exp.Schema) or statement.expression:
                continue
            relation = Relation.from_table(schema.this, dialect)
            if relation in discovered.schemas:
                discovered.problems.append(
                    SchemaProblem(path, f"{relation} is already defined")
                )
                continue
            discovered.schemas[relation] = tuple(
                Column(name=column.name, type=column.args["kind"].sql())
                for column in schema.expressions
                if isinstance(column, exp.ColumnDef)
            )
    return discovered


def _statements(text: str, dialect: str | None) -> Iterator[str]:
    start = 0
    for token in Dialect.get_or_raise(dialect).tokenize(text):
        if token.token_type == TokenType.SEMICOLON:
            if text[start : token.start].strip():
                yield text[start : token.start]
            start = token.end + 1
    if text[start:].strip():
        yield text[start:]
