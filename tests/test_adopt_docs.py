"""DOC-1: adopt section alone yields a working consumer project."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from sql_test.integrations.cli import main

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "minimal-consumer"
README = ROOT / "README.md"


def test_readme_adopt_section_has_a_full_consumer_pyproject():
    text = README.read_text()
    adopt = text.split("## Adopt in a consuming repository", 1)[1].split("## CLI", 1)[0]

    assert 'requires-python = ">=3.13"' in adopt
    assert "[project]" in adopt
    assert "[tool.uv]" in adopt
    assert "package = false" in adopt
    assert "[tool.sql-test]" in adopt
    assert "table_ref" in adopt and "sql_ref" in adopt
    assert "monorepo" in adopt.lower()
    assert "examples/minimal-consumer" in adopt
    assert "@main" in adopt  # bleeding-edge fallback until / beside floating tag


def test_minimal_consumer_example_discovers_and_passes_pytest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    assert EXAMPLE.is_dir(), "DOC-1 standalone sample missing"
    dest = tmp_path / "consumer"
    shutil.copytree(EXAMPLE, dest)

    pyproject = (dest / "pyproject.toml").read_text()
    assert "[project]" in pyproject
    assert "package = false" in pyproject
    assert 'requires-python = ">=3.13"' in pyproject
    assert "sql-test @ git+https://github.com/mvictoria/sql_test.git@v0" in pyproject

    mapping = (dest / "admin/config/lookup_sql_table_mapping.csv").read_text()
    assert mapping.splitlines()[0].strip() == "table_ref,sql_ref"

    assert main(["discover", str(dest)]) == 0
    out = capsys.readouterr().out
    assert "example" in out

    # Suite uses this env's installed sql-test (same pattern as CLI tests).
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=short"],
        check=False,
        cwd=dest,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
