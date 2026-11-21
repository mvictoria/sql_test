from pathlib import Path

import pytest

from sql_test.integrations.cli import main

FIXTURE = Path(__file__).parent / "fixtures/repos/lineage-demo"


def test_a_repository_without_config_is_reported(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    assert main(["app", str(tmp_path)]) == 1
    assert "has no pyproject.toml" in capsys.readouterr().err


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
