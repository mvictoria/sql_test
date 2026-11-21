from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from sql_test.engine import Relation
from sql_test.integrations.config import RepositoryConfig
from sql_test.testing import CaseSummary, discover_cases


@dataclass(frozen=True)
class Discovery:
    models: tuple[str, ...]
    sources: tuple[str, ...]
    cases: tuple[CaseSummary, ...]


def discover(repository: Path) -> Discovery:
    config = RepositoryConfig.load(repository)
    catalog = config.catalog()
    produced = {operation.writes for operation in catalog.operations}
    return Discovery(
        models=_names(produced),
        sources=_names(catalog.relations().keys() - produced),
        cases=tuple(discover_cases(config.cases)),
    )


def _names(relations: Iterable[Relation]) -> tuple[str, ...]:
    return tuple(sorted(str(relation) for relation in relations))
