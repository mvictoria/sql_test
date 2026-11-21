import subprocess
import sys
from pathlib import Path

import pytest

from sql_test.integrations.cli import main

FIXTURE = Path(__file__).parent / "fixtures/repos/lineage-demo"
LAKEHOUSE = Path(__file__).parent / "fixtures/repos/lakehouse-data-customer"


def test_discover_reports_a_repository_without_config(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    assert main(["discover", str(tmp_path)]) == 1
    assert "has no pyproject.toml" in capsys.readouterr().err


def test_app_starts_when_the_repository_has_no_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    calls: list[Path] = []

    def fake_serve(
        repository: Path, *, executor, host: str = "127.0.0.1", port: int = 8765
    ) -> None:
        calls.append(repository)

    monkeypatch.setattr("sql_test.integrations.cli.serve", fake_serve)

    assert main(["app", str(tmp_path)]) == 0
    assert calls == [tmp_path.resolve()]


def test_a_missing_repository_is_reported(capsys: pytest.CaptureFixture[str]):
    assert main(["app", "/no/such/repository"]) == 1
    assert "repository not found" in capsys.readouterr().err


def test_app_starts_the_server_for_the_repository_and_port(
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[tuple[Path, int, str]] = []

    def fake_serve(
        repository: Path, *, executor, host: str = "127.0.0.1", port: int = 8765
    ) -> None:
        calls.append((repository, port, type(executor).__name__))

    monkeypatch.setattr("sql_test.integrations.cli.serve", fake_serve)

    assert main(["app", str(FIXTURE), "--port", "9000"]) == 0
    assert calls == [(FIXTURE.resolve(), 9000, "DuckDBExecutor")]


def test_app_defaults_to_cwd_and_port_8765(monkeypatch: pytest.MonkeyPatch):
    calls: list[tuple[Path, int, str]] = []

    def fake_serve(
        repository: Path, *, executor, host: str = "127.0.0.1", port: int = 8765
    ) -> None:
        calls.append((repository, port, type(executor).__name__))

    monkeypatch.setattr("sql_test.integrations.cli.serve", fake_serve)
    monkeypatch.chdir(FIXTURE)

    assert main(["app"]) == 0
    assert calls == [(FIXTURE.resolve(), 8765, "DuckDBExecutor")]


def test_coverage_lists_untested_tables_before_tested_ones(
    capsys: pytest.CaptureFixture[str],
):
    assert main(["coverage", str(LAKEHOUSE)]) == 0
    out = capsys.readouterr().out
    lines = [line for line in out.splitlines() if line.strip()]
    # body lines after a header: table, tests, in-pipelines
    body = [line for line in lines if not line.lower().startswith("table")]
    tables = [line.split()[0] for line in body]
    assert "members" in tables
    assert "medicaid_members" in tables
    assert tables.index("members") < tables.index("medicaid_members")
    assert tables.index("lob") < tables.index("medicaid_members_named_alice")
    members = next(line for line in body if line.startswith("members"))
    assert members.split()[1:] == ["0", "0"]


def test_init_writes_a_consumer_skeleton_that_discovers_and_passes_pytest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    root = tmp_path / "demo"
    assert main(["init", str(root)]) == 0
    assert "Initialized" in capsys.readouterr().out
    assert (root / "pyproject.toml").is_file()
    assert (root / "admin/sqls/example.sql").is_file()
    assert (root / "admin/config/lookup_sql_table_mapping.csv").is_file()
    assert (root / "tests/conftest.py").is_file()
    assert (root / "tests/test_case_folders.py").is_file()
    assert main(["discover", str(root)]) == 0
    out = capsys.readouterr().out
    assert "example" in out
    assert "cases:" in out
    # Run the generated suite with this env's installed sql-test (no uv sync).
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=short"],
        check=False,
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_init_adds_sql_test_section_to_an_existing_pyproject(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "orders-data"\nversion = "1.0.0"\n'
    )
    assert main(["init", str(tmp_path)]) == 0
    text = (tmp_path / "pyproject.toml").read_text()
    assert 'name = "orders-data"' in text
    assert "[tool.sql-test]" in text
    assert 'sqls = "admin/sqls"' in text
    assert (tmp_path / "admin/sqls/example.sql").is_file()
    assert main(["discover", str(tmp_path)]) == 0
    assert "example" in capsys.readouterr().out


def test_init_keeps_existing_sql_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    sqls = tmp_path / "admin" / "sqls"
    sqls.mkdir(parents=True)
    ddl = "create table raw (id int);\ncreate table orders (id int);\n"
    (sqls / "ddl.sql").write_text(ddl)
    (sqls / "orders.sql").write_text("select id from raw\n")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "orders-data"\nversion = "0.1.0"\n'
    )

    assert main(["init", str(tmp_path)]) == 0
    assert (sqls / "ddl.sql").read_text() == ddl
    assert (sqls / "orders.sql").read_text() == "select id from raw\n"
    assert (sqls / "example.sql").is_file()
    assert "[tool.sql-test]" in (tmp_path / "pyproject.toml").read_text()
    assert main(["discover", str(tmp_path)]) == 0
    assert "example" in capsys.readouterr().out


def test_init_refuses_when_sql_test_is_already_configured(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    (tmp_path / "pyproject.toml").write_text(
        "[tool.sql-test]\n"
        'sqls = "admin/sqls"\n'
        'mapping = "admin/config/lookup_sql_table_mapping.csv"\n'
        'schemas = "admin/sqls"\n'
        'cases = "tests/cases"\n'
    )
    assert main(["init", str(tmp_path)]) == 1
    assert "[tool.sql-test]" in capsys.readouterr().err
