import importlib

import pytest


@pytest.mark.parametrize(
    "name",
    [
        "sql_test",
        "sql_test.engine",
        "sql_test.engine.discovery",
        "sql_test.engine.lineage",
        "sql_test.engine.execution",
        "sql_test.engine.comparison",
        "sql_test.engine.validation",
    ],
)
def test_package_imports(name):
    importlib.import_module(name)
