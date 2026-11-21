from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from functools import cached_property

from sql_test.engine.catalog.mapping import MappingProblem
from sql_test.engine.lineage.references import UnparseableSql, tables_read
from sql_test.engine.operation import Operation
from sql_test.engine.relation import Relation
from sql_test.engine.schema import Schema, SchemaProblem


@dataclass(frozen=True)
class Catalog:
    operations: tuple[Operation, ...] = ()
    schemas: Mapping[Relation, Schema] = field(default_factory=dict)
    problems: tuple[SchemaProblem | MappingProblem, ...] = ()

    def relations(self) -> frozenset[Relation]:
        """Every relation written by an operation, given a schema, or read by SQL."""
        return self._relations

    def resolve(self, name: str | Relation) -> Relation:
        """The relation `name` refers to; raises AmbiguousRelation if several fit."""
        reference = name if isinstance(name, Relation) else Relation.parse(name)
        return reference.resolve(self._by_name.get(reference.name, ()))

    def schema(self, relation: Relation) -> Schema | None:
        return self.schemas.get(relation)

    def producers(self, relation: Relation) -> tuple[Operation, ...]:
        return self._producers.get(relation, ())

    @cached_property
    def _relations(self) -> frozenset[Relation]:
        declared = _by_name(
            [*(operation.writes for operation in self.operations), *self.schemas]
        )
        relations = {relation for named in declared.values() for relation in named}
        for operation in self.operations:
            try:
                references = tables_read(operation.sql)
            except UnparseableSql:
                continue
            relations |= {
                reference.resolve(declared.get(reference.name, ()))
                for reference in references
            }
        return frozenset(relations)

    @cached_property
    def _by_name(self) -> dict[str, set[Relation]]:
        return _by_name(self._relations)

    @cached_property
    def _producers(self) -> dict[Relation, tuple[Operation, ...]]:
        producers: dict[Relation, list[Operation]] = {}
        for operation in self.operations:
            producers.setdefault(operation.writes, []).append(operation)
        return {relation: tuple(ops) for relation, ops in producers.items()}


def _by_name(relations: Iterable[Relation]) -> dict[str, set[Relation]]:
    """Relations keyed by name: a reference can only match relations of its name."""
    named: dict[str, set[Relation]] = {}
    for relation in relations:
        named.setdefault(relation.name, set()).add(relation)
    return named
