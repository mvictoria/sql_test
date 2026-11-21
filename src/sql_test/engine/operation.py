from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from sql_test.engine.relation import Relation


class Kind(StrEnum):
    FULL_LOAD = "full_load"
    INCREMENTAL = "incremental"
    APPEND = "append"
    MERGE = "merge"

    @classmethod
    def from_load_type(cls, load_type: str | None) -> Kind:
        """A mapping's load_type; anything but incremental, append, or merge is a full load."""
        value = (load_type or "").strip().lower()
        return (
            cls(value) if value in {"incremental", "append", "merge"} else cls.FULL_LOAD
        )


@dataclass(frozen=True)
class Operation:
    sql_file: Path
    writes: Relation
    kind: Kind

    @property
    def sql(self) -> str:
        return self.sql_file.read_text()
