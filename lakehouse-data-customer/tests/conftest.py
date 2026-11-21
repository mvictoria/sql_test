from pathlib import Path

import pytest

from sql_test.engine import Engine
from sql_test.executors.duckdb import DuckDBExecutor
from sql_test.integrations.config import RepositoryConfig

CONFIG = RepositoryConfig.load(Path(__file__).parent.parent)


@pytest.fixture(scope="session")
def engine():
    return Engine(catalog=CONFIG.catalog(), executor=DuckDBExecutor)
