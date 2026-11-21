from collections.abc import Collection
from dataclasses import dataclass
from enum import StrEnum

from sql_test.engine.catalog import Catalog
from sql_test.engine.lineage.references import UnparseableSql, tables_read
from sql_test.engine.operation import Operation
from sql_test.engine.relation import Relation


class SourceReason(StrEnum):
    NOT_PRODUCED = "not produced in this repository"
    UNPARSEABLE_SQL = "its SQL cannot be parsed"
    NO_SCHEMA = "it has no schema"


@dataclass(frozen=True)
class Lineage:
    target: Relation
    producers: dict[Relation, tuple[Operation, ...]]
    reads: dict[Operation, set[Relation]]
    source_reasons: dict[Relation, SourceReason]

    @property
    def models(self) -> set[Relation]:
        return set(self.producers)

    @property
    def sources(self) -> set[Relation]:
        return set(self.source_reasons)

    def projection(self) -> dict[Relation, set[Relation]]:
        built_from: dict[Relation, set[Relation]] = {
            relation: set() for relation in self.models | self.sources
        }
        for operation, reads in self.reads.items():
            built_from[operation.writes] |= reads
        return built_from


def upstream_lineage(
    target: Relation, catalog: Catalog, boundaries: Collection[Relation] = ()
) -> Lineage:
    """Walk up from `target`, not past an execution boundary in `boundaries`."""
    reached: dict[Relation, tuple[Operation, ...]] = {}
    reads: dict[Operation, set[Relation]] = {}
    source_reasons: dict[Relation, SourceReason] = {}
    pending = [target]
    while pending:
        current = pending.pop()
        if current in reached or current in source_reasons or current in boundaries:
            continue
        producers = catalog.producers(current)
        if not producers:
            source_reasons[current] = SourceReason.NOT_PRODUCED
            continue
        if catalog.schema(current) is None:
            source_reasons[current] = SourceReason.NO_SCHEMA
            continue
        try:
            current_reads = {
                operation: {
                    catalog.resolve(reference)
                    for reference in tables_read(operation.sql)
                }
                for operation in producers
            }
        except UnparseableSql:
            source_reasons[current] = SourceReason.UNPARSEABLE_SQL
            continue
        reached[current] = producers
        reads |= current_reads
        for relations in current_reads.values():
            pending.extend(relations)
    return Lineage(
        target=target, producers=reached, reads=reads, source_reasons=source_reasons
    )
