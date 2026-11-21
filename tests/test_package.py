import importlib

import pytest


@pytest.mark.parametrize(
    "name",
    [
        "sql_test",
        "sql_test.engine",
        "sql_test.engine.catalog",
        "sql_test.engine.lineage",
        "sql_test.engine.planner",
        "sql_test.engine.executor",
        "sql_test.executors",
        "sql_test.executors.duckdb",
        "sql_test.testing",
        "sql_test.testing.cases",
        "sql_test.testing.comparison",
        "sql_test.integrations",
        "sql_test.integrations.pytest_plugin",
    ],
)
def test_package_imports(name):
    importlib.import_module(name)
