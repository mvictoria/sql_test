from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from sql_test.engine.relation import Relation


class Kind(StrEnum):
    FULL_LOAD = "full_load"


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
