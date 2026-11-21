from pathlib import Path

import pytest

from sql_test.engine import Engine
from sql_test.engine.catalog.adapters import mapped_sql_folder
from sql_test.executors.duckdb import DuckDBExecutor

ADMIN = Path(__file__).parent.parent / "admin"


@pytest.fixture(scope="session")
def engine():
    return Engine(
        catalog=mapped_sql_folder(
            sqls=ADMIN / "sqls",
            mapping=ADMIN / "config" / "lookup_sql_table_mapping.csv",
        ),
        executor=DuckDBExecutor,
    )
