from pathlib import Path

import pytest

from sql_test.integrations.cli import main


def test_a_repository_without_config_is_reported(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    for command in ("discover", "app"):
        assert main([command, str(tmp_path)]) == 1
        assert "has no pyproject.toml" in capsys.readouterr().err
