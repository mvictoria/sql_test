from collections import defaultdict
from dataclasses import dataclass

from sql_test.engine.catalog import Catalog
from sql_test.engine.lineage.references import tables_read
from sql_test.engine.operation import Operation
from sql_test.engine.relation import Relation


@dataclass(frozen=True)
class Lineage:
    target: Relation
    producers: dict[Relation, tuple[Operation, ...]]
    reads: dict[Operation, set[Relation]]

    @property
    def models(self) -> set[Relation]:
        return set(self.producers)

    @property
    def sources(self) -> set[Relation]:
        read = {self.target}.union(*self.reads.values())
        return read - self.models

    def projection(self) -> dict[Relation, set[Relation]]:
        built_from: dict[Relation, set[Relation]] = {
            relation: set() for relation in self.models | self.sources
        }
        for operation, reads in self.reads.items():
            built_from[operation.writes] |= reads
        return built_from


def upstream_lineage(target: Relation, catalog: Catalog) -> Lineage:
    producers: dict[Relation, list[Operation]] = defaultdict(list)
    for operation in catalog.operations:
        producers[operation.writes].append(operation)
    known = catalog.relations().keys()
    reached: dict[Relation, tuple[Operation, ...]] = {}
    reads: dict[Operation, set[Relation]] = {}
    pending = [target]
    while pending:
        current = pending.pop()
        if current in reached or current not in producers:
            continue
        reached[current] = tuple(producers[current])
        for operation in reached[current]:
            reads[operation] = {
                reference.resolve(known) for reference in tables_read(operation.sql)
            }
            pending.extend(reads[operation])
    return Lineage(target=target, producers=reached, reads=reads)
