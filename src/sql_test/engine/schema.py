from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Self

from sqlglot import exp

from sql_test.engine.relation import Relation

_Type = exp.DataType.Type
_DECIMALS = {_Type.DECIMAL, _Type.BIGDECIMAL, _Type.UDECIMAL, _Type.MONEY}
_BOOLEANS = {"true": True, "false": False}


@dataclass(frozen=True)
class Column:
    name: str
    type: str

    @classmethod
    def parse(cls, name: str, type: str, dialect: str | None = None) -> Self:
        return cls(name=name, type=exp.DataType.build(type, dialect=dialect).sql())

    def cast(self, text: str | None) -> Any:
        """Read `text` as this column's type; raises ValueError if it is not one."""
        if text is None:
            return None
        kind = exp.DataType.build(self.type).this
        if kind in exp.DataType.INTEGER_TYPES:
            return int(text)
        if kind in _DECIMALS:
            try:
                return Decimal(text)
            except InvalidOperation as error:
                raise ValueError(text) from error
        if kind in exp.DataType.REAL_TYPES:
            return float(text)
        if kind is _Type.BOOLEAN:
            if text.lower() not in _BOOLEANS:
                raise ValueError(text)
            return _BOOLEANS[text.lower()]
        if kind is _Type.DATE:
            return date.fromisoformat(text)
        if kind in exp.DataType.TEMPORAL_TYPES:
            return datetime.fromisoformat(text)
        return text


type Schema = tuple[Column, ...]


@dataclass(frozen=True)
class SchemaProblem:
    file: Path
    reason: str


@dataclass
class DiscoveredSchemas:
    schemas: dict[Relation, Schema] = field(default_factory=dict)
    problems: list[SchemaProblem] = field(default_factory=list)
