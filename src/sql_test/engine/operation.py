from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from sql_test.engine.relation import Relation


class Kind(StrEnum):
    FULL_LOAD = "full_load"
    MERGE = "merge"

    @classmethod
    def from_load_type(cls, load_type: str | None) -> Kind:
        """A mapping's load_type; only merge is recognized for now, else full load."""
        value = (load_type or "").strip().lower()
        return cls.MERGE if value == "merge" else cls.FULL_LOAD


class UnsupportedProducer(Exception):
    """A producer whose SQL kind is not supported yet (not a SELECT full load)."""


@dataclass(frozen=True)
class Operation:
    sql_file: Path
    writes: Relation
    kind: Kind

    @property
    def sql(self) -> str:
        return self.sql_file.read_text()
