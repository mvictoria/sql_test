from dataclasses import dataclass, field
from pathlib import Path
from typing import Self

from sqlglot import exp

from sql_test.engine.relation import Relation


@dataclass(frozen=True)
class Column:
    name: str
    type: str

    @classmethod
    def parse(cls, name: str, type: str, dialect: str | None = None) -> Self:
        return cls(name=name, type=exp.DataType.build(type, dialect=dialect).sql())


type Schema = tuple[Column, ...]


@dataclass(frozen=True)
class SchemaProblem:
    file: Path
    reason: str


@dataclass
class DiscoveredSchemas:
    schemas: dict[Relation, Schema] = field(default_factory=dict)
    problems: list[SchemaProblem] = field(default_factory=list)
