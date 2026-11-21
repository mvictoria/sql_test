from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from typing import Self

from sqlglot import exp
from sqlglot.optimizer.normalize_identifiers import normalize_identifiers


class AmbiguousRelation(Exception):
    pass


@dataclass(frozen=True)
class Relation:
    name: str
    schema: str | None = None
    catalog: str | None = None

    @classmethod
    def parse(cls, text: str, dialect: str = "duckdb") -> Relation:
        return _parse(text, dialect)

    @classmethod
    def from_table(cls, table: exp.Table, dialect: str | None = "duckdb") -> Self:
        table = normalize_identifiers(table.copy(), dialect=dialect)
        return cls(
            name=table.name, schema=table.db or None, catalog=table.catalog or None
        )

    def __str__(self) -> str:
        return ".".join(part for part in (self.catalog, self.schema, self.name) if part)

    def matches(self, other: Relation) -> bool:
        return (
            self.name == other.name
            and self.schema in (None, other.schema)
            and self.catalog in (None, other.catalog)
        )

    def resolve(self, known: Iterable[Relation]) -> Relation:
        candidates = sorted({r for r in known if self.matches(r)}, key=str)
        if len(candidates) > 1:
            names = ", ".join(map(str, candidates))
            raise AmbiguousRelation(f"{self} could be any of: {names}")
        return candidates[0] if candidates else self


@lru_cache(maxsize=4096)
def _parse(text: str, dialect: str) -> Relation:
    return Relation.from_table(exp.to_table(text, dialect=dialect), dialect)
