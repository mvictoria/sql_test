from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

import sqlglot
from sqlglot import exp
from sqlglot.dialects.dialect import Dialect
from sqlglot.errors import SqlglotError
from sqlglot.tokens import TokenType

from sql_test.engine.relation import Relation
from sql_test.engine.schema import Column, DiscoveredSchemas, Schema, SchemaProblem


def read_ddl_schemas(folder: Path, dialect: str | None = None) -> DiscoveredSchemas:
    discovered = DiscoveredSchemas()
    for path in sorted(folder.rglob("*.sql")):
        for definition in _definitions(path.read_text(), dialect):
            if isinstance(definition, str):
                discovered.problems.append(SchemaProblem(path, definition))
                continue
            relation, schema = definition
            if relation in discovered.schemas:
                discovered.problems.append(
                    SchemaProblem(path, f"{relation} is already defined")
                )
                continue
            discovered.schemas[relation] = schema
    return discovered


# Must exceed the files in a repository: a rebuild reads them in order, so a
# smaller LRU evicts each entry before it is needed again and never hits.
@lru_cache(maxsize=65536)
def _definitions(
    text: str, dialect: str | None
) -> tuple[tuple[Relation, Schema] | str, ...]:
    """The tables `text` creates, and why any statement does not parse."""
    try:
        statements = list(_statements(text, dialect))
    except SqlglotError as error:
        return (str(error),)
    definitions: list[tuple[Relation, Schema] | str] = []
    for statement_text in statements:
        try:
            statement = sqlglot.parse_one(statement_text, read=dialect)
        except SqlglotError as error:
            definitions.append(str(error))
            continue
        if not isinstance(statement, exp.Create):
            continue
        schema = statement.this
        if not isinstance(schema, exp.Schema) or statement.expression:
            continue
        definitions.append(
            (
                Relation.from_table(schema.this, dialect),
                tuple(
                    Column(name=column.name, type=column.args["kind"].sql())
                    for column in schema.expressions
                    if isinstance(column, exp.ColumnDef)
                ),
            )
        )
    return tuple(definitions)


def _statements(text: str, dialect: str | None) -> Iterator[str]:
    start = 0
    for token in Dialect.get_or_raise(dialect).tokenize(text):
        if token.token_type == TokenType.SEMICOLON:
            if text[start : token.start].strip():
                yield text[start : token.start]
            start = token.end + 1
    if text[start:].strip():
        yield text[start:]
