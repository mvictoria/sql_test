from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
SAMPLE_CALLER = (
    ROOT / "lakehouse-data-customer" / ".github" / "workflows" / "data-tests.yml"
)


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def _on(workflow: dict) -> dict:
    # GitHub accepts bare `on:`; PyYAML 1.1 may load it as True unless quoted.
    return workflow.get("on") or workflow[True]


def test_data_tests_is_reusable_and_installs_from_git_workflow_sha():
    workflow = _load(WORKFLOWS / "data-tests.yml")

    assert "workflow_call" in _on(workflow)
    inputs = _on(workflow)["workflow_call"].get("inputs") or {}
    assert "working-directory" in inputs
    assert inputs["working-directory"].get("default") == "."

    job = workflow["jobs"]["data-tests"]
    steps = job["steps"]
    install = next(
        s for s in steps if s.get("name") == "Install sql-test from workflow ref"
    )
    assert "github.workflow_sha" in install["run"]
    assert "git+https://github.com/mvictoria/sql_test.git@" in install["run"]
    assert "uv pip install" in install["run"]

    pytest_step = next(s for s in steps if s.get("name") == "Pytest")
    assert pytest_step["run"].strip() == "uv run pytest"
    assert pytest_step.get("working-directory") == "${{ inputs.working-directory }}"


def test_sample_repository_calls_reusable_workflow():
    caller = _load(SAMPLE_CALLER)
    job = caller["jobs"]["data-tests"]
    assert (
        job["uses"].endswith("/.github/workflows/data-tests.yml@v0")
        or job["uses"] == "mvictoria/sql_test/.github/workflows/data-tests.yml@v0"
    )


def test_tool_ci_calls_reusable_workflow_for_sample():
    ci = _load(WORKFLOWS / "ci.yml")
    job = ci["jobs"]["sample-data-tests"]
    assert job["uses"] == "./.github/workflows/data-tests.yml"
    assert job["with"]["working-directory"] == "lakehouse-data-customer"
