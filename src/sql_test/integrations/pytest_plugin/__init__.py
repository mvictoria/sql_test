from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from sql_test.engine import Engine
from sql_test.engine.catalog.adapters import mapped_sql_folder
from sql_test.executors.duckdb import DuckDBExecutor
from sql_test.integrations.discover import CASES, MAPPING, SQLS
from sql_test.testing.run import CaseResult, run_case


def pytest_collect_directory(path: Path, parent: pytest.Collector) -> Any:
    repository = path.parent
    if path.name == CASES.name and (repository / SQLS).is_dir():
        return CasesDirectory.from_parent(parent, path=path)
    return None


class CasesDirectory(pytest.Directory):
    def collect(self) -> Iterator[CaseItem]:
        repository = self.path.parent
        engine = Engine(
            catalog=mapped_sql_folder(repository / SQLS, repository / MAPPING),
            executor=DuckDBExecutor,
        )
        for target in sorted(path for path in self.path.iterdir() if path.is_dir()):
            for case in sorted(path for path in target.iterdir() if path.is_dir()):
                yield CaseItem.from_parent(
                    self, name=f"{target.name}/{case.name}", folder=case, engine=engine
                )


class CaseFailed(Exception):
    def __init__(self, result: CaseResult) -> None:
        super().__init__(result.report())
        self.result = result


class CaseItem(pytest.Item):
    def __init__(self, *, folder: Path, engine: Engine, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.folder = folder
        self.engine = engine

    def runtest(self) -> None:
        result = run_case(self.folder, self.engine)
        if not result.passed:
            raise CaseFailed(result)

    def repr_failure(
        self, excinfo: pytest.ExceptionInfo[BaseException], style=None
    ) -> Any:
        if isinstance(excinfo.value, CaseFailed):
            return excinfo.value.result.report()
        return super().repr_failure(excinfo, style)

    def reportinfo(self) -> tuple[Path, int | None, str]:
        return self.folder, None, self.name
