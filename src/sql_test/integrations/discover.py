from dataclasses import dataclass
from pathlib import Path

from sqlglot.errors import ParseError

from sql_test.engine.catalog.mapping import read_operations
from sql_test.engine.lineage.references import tables_read
from sql_test.engine.relation import Relation
from sql_test.testing.cases import CaseSummary, discover_cases

# Sample-repo convention until CFG-1.
SQLS = Path("admin") / "sqls"
MAPPING = Path("admin") / "config" / "lookup_sql_table_mapping.csv"
CASES = Path("cases")


@dataclass(frozen=True)
class Discovery:
    models: tuple[str, ...]
    sources: tuple[str, ...]
    cases: tuple[CaseSummary, ...]


def discover(repository: Path) -> Discovery:
    repository = repository.resolve()
    operations = read_operations(repository / MAPPING, repository / SQLS)
    produced = {operation.writes for operation in operations}
    referenced: set[Relation] = set()
    sources: set[Relation] = set()
    for operation in operations:
        try:
            referenced |= tables_read(operation.sql)
        except ParseError:
            sources.add(operation.writes)
    sources |= {relation for relation in referenced if relation not in produced}
    return Discovery(
        models=tuple(sorted(str(relation) for relation in produced)),
        sources=tuple(sorted(str(relation) for relation in sources)),
        cases=tuple(discover_cases(repository / CASES)),
    )
