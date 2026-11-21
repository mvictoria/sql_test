from dataclasses import dataclass
from pathlib import Path

from sqlglot.errors import ParseError

from sql_test.engine.catalog.mapping import read_producers
from sql_test.engine.lineage.references import tables_read
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
    producers = read_producers(repository / MAPPING, repository / SQLS)
    referenced: set[str] = set()
    sources: set[str] = set()
    for table, path in producers.items():
        try:
            referenced |= tables_read(path.read_text())
        except ParseError:
            sources.add(table)
    sources |= referenced - set(producers)
    return Discovery(
        models=tuple(sorted(producers)),
        sources=tuple(sorted(sources)),
        cases=tuple(discover_cases(repository / CASES)),
    )
