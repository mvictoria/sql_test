import sys
from collections.abc import Iterator
from types import ModuleType

import pytest

pytest_plugins = ["nicegui.testing.user_plugin"]


@pytest.fixture(autouse=True)
def keep_package_modules() -> Iterator[None]:
    """NiceGUI's `user` teardown drops the module of every page function, and its
    parents, from `sys.modules`; that would split `sql_test` into stale and fresh
    copies for later tests. Restore the package after each test."""
    saved: dict[str, ModuleType] = {
        name: module
        for name, module in sys.modules.items()
        if name == "sql_test" or name.startswith("sql_test.")
    }
    yield
    sys.modules.update(saved)
