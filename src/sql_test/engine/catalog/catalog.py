from dataclasses import dataclass, field

from sql_test.engine.lineage.references import UnparseableSql, tables_read
from sql_test.engine.operation import Operation
from sql_test.engine.relation import Relation
from sql_test.engine.schema import Schema, SchemaProblem


@dataclass
class Catalog:
    operations: list[Operation] = field(default_factory=list)
    schemas: dict[Relation, Schema] = field(default_factory=dict)
    problems: list[SchemaProblem] = field(default_factory=list)

    def relations(self) -> set[Relation]:
        """Every relation written by an operation, given a schema, or read by SQL."""
        declared = {operation.writes for operation in self.operations}
        declared |= self.schemas.keys()
        relations = set(declared)
        for operation in self.operations:
            try:
                references = tables_read(operation.sql)
            except UnparseableSql:
                continue
            relations |= {reference.resolve(declared) for reference in references}
        return relations

    def resolve(self, name: str) -> Relation:
        """The relation `name` refers to; raises AmbiguousRelation if several fit."""
        return Relation.parse(name).resolve(self.relations())

    def schema(self, relation: Relation) -> Schema | None:
        return self.schemas.get(relation)

    def producers(self, relation: Relation) -> tuple[Operation, ...]:
        return tuple(
            operation for operation in self.operations if operation.writes == relation
        )
