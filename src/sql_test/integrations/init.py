"""Write a minimal consuming-repository skeleton (`sql-test init`)."""

from __future__ import annotations

from pathlib import Path

_RELATIVE = {
    "sqls": "admin/sqls",
    "mapping": "admin/config/lookup_sql_table_mapping.csv",
    "schemas": "admin/sqls",
    "cases": "tests/cases",
}

_PYPROJECT = """\
[project]
name = "sql-test-demo"
version = "0.0.0"
requires-python = ">=3.13"
dependencies = [
    "sql-test @ git+https://github.com/mvictoria/sql_test.git@v0",
    "pytest>=9",
]

[tool.uv]
package = false

[tool.sql-test]
sqls = "admin/sqls"
mapping = "admin/config/lookup_sql_table_mapping.csv"
schemas = "admin/sqls"
cases = "tests/cases"
"""

_DDL = """\
create table raw (id int);
create table example (id int);
"""

_EXAMPLE_SQL = """\
select id from raw
"""

_MAPPING = """\
table_ref,sql_ref
example,example.sql
"""

_RAW_CSV = """\
id
1
"""

_EXPECTED_CSV = """\
id
1
"""

_CONFTEST = """\
from pathlib import Path

import pytest

from sql_test.engine import Engine
from sql_test.executors import DuckDBExecutor
from sql_test.integrations.config import RepositoryConfig

CONFIG = RepositoryConfig.load(Path(__file__).parent.parent)


@pytest.fixture(scope="session")
def engine():
    return Engine(catalog=CONFIG.catalog(), executor=DuckDBExecutor())
"""

_TEST_CASE_FOLDERS = """\
from pathlib import Path

import pytest

from sql_test.integrations.config import RepositoryConfig
from sql_test.testing import case_folders, case_id, run_case

CASES = RepositoryConfig.load(Path(__file__).parent.parent).cases


@pytest.mark.parametrize("case", case_folders(CASES), ids=case_id)
def test_case(case, engine):
    result = run_case(case, engine)
    assert result.passed, result.report()
"""


class InitError(Exception):
    pass


def init_repository(path: Path) -> Path:
    """Create a consumer skeleton at `path`; raise InitError if unsafe to write."""
    root = path.resolve()
    if (root / "pyproject.toml").is_file():
        raise InitError(f"{root} already has a pyproject.toml")
    root.mkdir(parents=True, exist_ok=True)

    sqls = root / _RELATIVE["sqls"]
    sqls.mkdir(parents=True, exist_ok=True)
    (sqls / "ddl.sql").write_text(_DDL)
    (sqls / "example.sql").write_text(_EXAMPLE_SQL)

    mapping = root / _RELATIVE["mapping"]
    mapping.parent.mkdir(parents=True, exist_ok=True)
    mapping.write_text(_MAPPING)

    case = root / _RELATIVE["cases"] / "example" / "passthrough"
    case.mkdir(parents=True, exist_ok=True)
    (case / "raw.csv").write_text(_RAW_CSV)
    (case / "expected.csv").write_text(_EXPECTED_CSV)

    tests = root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "conftest.py").write_text(_CONFTEST)
    (tests / "test_case_folders.py").write_text(_TEST_CASE_FOLDERS)

    (root / "pyproject.toml").write_text(_PYPROJECT)
    return root
