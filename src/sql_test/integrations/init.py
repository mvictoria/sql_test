"""Write a minimal consuming-repository skeleton (`sql-test init`)."""

from __future__ import annotations

from pathlib import Path

import tomlkit

from sql_test.integrations.config import PATH_NAMES, TABLE

_RELATIVE = {
    "sqls": "admin/sqls",
    "mapping": "admin/config/lookup_sql_table_mapping.csv",
    "schemas": "admin/sqls",
    "cases": "tests/cases",
}

_SQL_TEST_DEP = "sql-test @ git+https://github.com/mvictoria/sql_test.git@v0"
_PYTEST_DEP = "pytest>=9"

_NEW_PYPROJECT = f"""\
[project]
name = "sql-test-demo"
version = "0.0.0"
requires-python = ">=3.13"
dependencies = [
    "{_SQL_TEST_DEP}",
    "{_PYTEST_DEP}",
]

[tool.uv]
package = false
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

_DATA_TESTS_WORKFLOW = """\
name: Data tests

"on":
  push:
    branches: [main]
  pull_request:

permissions:
  contents: read

jobs:
  data-tests:
    uses: mvictoria/sql_test/.github/workflows/data-tests.yml@v0
"""


class InitError(Exception):
    pass


def init_repository(path: Path) -> Path:
    """Create a consumer skeleton at `path`; raise InitError if already configured."""
    root = path.resolve()
    root.mkdir(parents=True, exist_ok=True)
    pyproject = root / "pyproject.toml"
    if pyproject.is_file() and _has_sql_test_table(pyproject):
        raise InitError(f"{pyproject} already has a [tool.{TABLE}] table")

    _write_layout(root)
    _write_or_merge_pyproject(pyproject)
    return root


def _has_sql_test_table(pyproject: Path) -> bool:
    document = tomlkit.parse(pyproject.read_text())
    tool = document.get("tool")
    return isinstance(tool, dict) and TABLE in tool


def _write_or_merge_pyproject(pyproject: Path) -> None:
    if pyproject.is_file():
        document = tomlkit.parse(pyproject.read_text())
        _ensure_consumer_dependencies(document)
    else:
        document = tomlkit.parse(_NEW_PYPROJECT)
    tool = document.setdefault("tool", tomlkit.table())
    table = tool.setdefault(TABLE, tomlkit.table())
    for name in PATH_NAMES:
        table[name] = _RELATIVE[name]
    pyproject.write_text(tomlkit.dumps(document))


def _ensure_consumer_dependencies(document: tomlkit.TOMLDocument) -> None:
    """Add sql-test and pytest when missing so `uv sync && uv run pytest` can work."""
    project = document.setdefault("project", tomlkit.table())
    deps = project.get("dependencies")
    if deps is None:
        deps = tomlkit.array()
        project["dependencies"] = deps
    entries = [str(item).strip().strip('"').strip("'") for item in deps]
    if not any(entry.startswith("sql-test") for entry in entries):
        deps.append(_SQL_TEST_DEP)
    if not any(entry.startswith("pytest") for entry in entries):
        deps.append(_PYTEST_DEP)


def _write_layout(root: Path) -> None:
    sqls = root / _RELATIVE["sqls"]
    _write_if_absent(sqls / "ddl.sql", _DDL)
    _write_if_absent(sqls / "example.sql", _EXAMPLE_SQL)

    mapping = root / _RELATIVE["mapping"]
    _write_if_absent(mapping, _MAPPING)

    case = root / _RELATIVE["cases"] / "example" / "passthrough"
    _write_if_absent(case / "raw.csv", _RAW_CSV)
    _write_if_absent(case / "expected.csv", _EXPECTED_CSV)

    tests = root / "tests"
    _write_if_absent(tests / "conftest.py", _CONFTEST)
    _write_if_absent(tests / "test_case_folders.py", _TEST_CASE_FOLDERS)

    _write_if_absent(
        root / ".github" / "workflows" / "data-tests.yml",
        _DATA_TESTS_WORKFLOW,
    )


def _write_if_absent(path: Path, text: str) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
