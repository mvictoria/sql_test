from pathlib import Path

import pytest

from sql_test.integrations.config import ConfigError, RepositoryConfig

FIXTURE = Path(__file__).parent / "fixtures" / "repos" / "lakehouse-data-customer"


def test_paths_are_read_from_pyproject_relative_to_the_repository(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        "[tool.sql-test]\n"
        'sqls = "sql"\n'
        'mapping = "config/mapping.csv"\n'
        'schemas = "ddl"\n'
        'cases = "tests/fixtures/cases"\n'
    )

    config = RepositoryConfig.load(tmp_path)

    assert config.sqls == tmp_path / "sql"
    assert config.mapping == tmp_path / "config" / "mapping.csv"
    assert config.schemas == tmp_path / "ddl"
    assert config.cases == tmp_path / "tests" / "fixtures" / "cases"


def test_the_sample_repository_has_a_config():
    config = RepositoryConfig.load(FIXTURE)

    assert config.sqls == FIXTURE.resolve() / "admin" / "sqls"
    assert config.cases == FIXTURE.resolve() / "tests" / "cases"


def test_a_repository_without_pyproject_is_an_error(tmp_path: Path):
    with pytest.raises(ConfigError, match="no pyproject.toml"):
        RepositoryConfig.load(tmp_path)


def test_a_pyproject_without_the_table_is_an_error(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')

    with pytest.raises(ConfigError, match=r"no \[tool.sql-test\] table"):
        RepositoryConfig.load(tmp_path)


def test_missing_settings_are_named(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text('[tool.sql-test]\nsqls = "sql"\n')

    with pytest.raises(ConfigError, match="missing: cases, mapping, schemas"):
        RepositoryConfig.load(tmp_path)


def test_saving_cases_leaves_the_rest_of_pyproject_byte_for_byte_unchanged(
    tmp_path: Path,
):
    import shutil

    repo = tmp_path / "repo"
    shutil.copytree(FIXTURE, repo)
    (repo / "tests" / "cases").rename(repo / "other_cases")
    pyproject = repo / "pyproject.toml"
    before = (
        "# keep me\n"
        "[project]\n"
        'name = "demo"\n'
        "\n"
        "[tool.ruff]\n"
        "line-length = 88\n"
        "\n"
        "[tool.sql-test]\n"
        'sqls = "admin/sqls"\n'
        'mapping = "admin/config/lookup_sql_table_mapping.csv"\n'
        'schemas = "admin/sqls"\n'
        'cases = "tests/cases"\n'
        "\n"
        "# trailing\n"
    )
    pyproject.write_text(before)

    RepositoryConfig.write(
        repo,
        {
            "sqls": "admin/sqls",
            "mapping": "admin/config/lookup_sql_table_mapping.csv",
            "schemas": "admin/sqls",
            "cases": "other_cases",
        },
    )

    after = pyproject.read_text()
    assert 'cases = "other_cases"' in after
    without_cases = lambda text: "\n".join(
        line for line in text.splitlines() if not line.startswith("cases =")
    )
    assert without_cases(before) == without_cases(after)
    assert RepositoryConfig.load(repo).cases == repo / "other_cases"
