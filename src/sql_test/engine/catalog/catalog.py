from dataclasses import dataclass, field
from enum import StrEnum

from sql_test.engine.lineage.references import UnparseableSql, tables_read
from sql_test.engine.operation import Operation
from sql_test.engine.relation import Relation
from sql_test.engine.schema import Schema, SchemaProblem


class Evidence(StrEnum):
    DECLARED = "declared"
    INFERRED = "inferred"


@dataclass
class Catalog:
    operations: list[Operation] = field(default_factory=list)
    schemas: dict[Relation, Schema] = field(default_factory=dict)
    problems: list[SchemaProblem] = field(default_factory=list)

    def relations(self) -> dict[Relation, Evidence]:
        declared = {operation.writes for operation in self.operations}
        declared |= self.schemas.keys()
        relations = dict.fromkeys(declared, Evidence.DECLARED)
        for operation in self.operations:
            try:
                references = tables_read(operation.sql)
            except UnparseableSql:
                continue
            for reference in references:
                relations.setdefault(reference.resolve(declared), Evidence.INFERRED)
        return relations
