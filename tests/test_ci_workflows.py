from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
SAMPLE_CALLERS = (
    ROOT / "examples" / "minimal-consumer" / ".github" / "workflows" / "data-tests.yml",
    ROOT
    / "examples"
    / "lakehouse-data-customer"
    / ".github"
    / "workflows"
    / "data-tests.yml",
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
    assert install.get("working-directory") == "${{ inputs.working-directory }}"
    assert "github.workflow_sha" in install["run"]
    assert "git+https://github.com/mvictoria/sql_test.git@" in install["run"]
    assert "uv pip install" in install["run"]

    pytest_step = next(s for s in steps if s.get("name") == "Pytest")
    assert pytest_step["run"].strip() == "uv run pytest"
    assert pytest_step.get("working-directory") == "${{ inputs.working-directory }}"


def test_sample_repositories_call_reusable_workflow():
    for path in SAMPLE_CALLERS:
        caller = _load(path)
        job = caller["jobs"]["data-tests"]
        assert (
            job["uses"].endswith("/.github/workflows/data-tests.yml@v0")
            or job["uses"] == "mvictoria/sql_test/.github/workflows/data-tests.yml@v0"
        ), path


def test_tool_ci_calls_reusable_workflow_for_sample():
    ci = _load(WORKFLOWS / "ci.yml")
    job = ci["jobs"]["sample-data-tests"]
    assert job["uses"] == "./.github/workflows/data-tests.yml"
    assert (
        job["with"]["working-directory"]
        == "tests/fixtures/repos/lakehouse-data-customer"
    )


def test_tool_ci_runs_on_pull_requests_only():
    ci = _load(WORKFLOWS / "ci.yml")
    assert "push" not in _on(ci)
    pull_request = _on(ci)["pull_request"]
    assert pull_request["paths-ignore"] == ["**/*.md"]


def test_tool_ci_tests_python_313_through_315():
    ci = _load(WORKFLOWS / "ci.yml")
    job = ci["jobs"]["test"]
    assert job["strategy"]["matrix"]["python-version"] == [
        "3.13",
        "3.14",
        "3.15",
    ]

    install_uv = next(s for s in job["steps"] if s.get("name") == "Install uv")
    assert install_uv["with"]["python-version"] == "${{ matrix.python-version }}"

    checks = next(s for s in job["steps"] if s.get("name") == "Checks")
    assert checks["if"] == "matrix.python-version == '3.15'"

    pyproject = (ROOT / "pyproject.toml").read_text()
    assert 'requires-python = ">=3.13"' in pyproject
    assert 'target-version = "py313"' in pyproject


def test_cd_tags_main_from_pr_title_then_releases_in_the_same_run():
    """GITHUB_TOKEN tag pushes do not start workflows; publish in tag-from-pr."""
    workflow = _load(WORKFLOWS / "cd.yml")
    push = _on(workflow)["push"]
    assert "main" in push["branches"]
    assert "v[0-9]+.[0-9]+.[0-9]+" in push["tags"]

    tag_job = workflow["jobs"]["tag-from-pr"]
    assert "refs/heads/main" in tag_job["if"]
    assert tag_job["permissions"]["pull-requests"] == "read"
    tag_step = next(
        s for s in tag_job["steps"] if s.get("name") == "Tag release from PR title"
    )
    assert tag_step["id"] == "bump"
    assert "scripts/cd_bump.py" in tag_step["run"]
    assert "github.sha" in tag_step["run"]
    assert "GITHUB_OUTPUT" in tag_step["run"]

    for name in (
        "Install uv",
        "Build",
        "Create GitHub Release",
        "Move major version tag",
    ):
        step = next(s for s in tag_job["steps"] if s.get("name") == name)
        assert "steps.bump.outputs.tag" in step["if"]
    build = next(s for s in tag_job["steps"] if s.get("name") == "Build")
    assert "uv build" in build["run"]
    release = next(
        s for s in tag_job["steps"] if s.get("name") == "Create GitHub Release"
    )
    assert "dist/" in release["run"]
    move = next(
        s for s in tag_job["steps"] if s.get("name") == "Move major version tag"
    )
    assert "git tag -f" in move["run"]
    assert "git push" in move["run"] and "--force" in move["run"]

    job = workflow["jobs"]["release"]
    assert "refs/tags/v" in job["if"]
    assert job["permissions"]["contents"] == "write"


def test_package_version_is_dynamic_from_git():
    pyproject = (ROOT / "pyproject.toml").read_text()
    assert 'dynamic = ["version"]' in pyproject
    assert 'source = "uv-dynamic-versioning"' in pyproject
    assert "version = " not in pyproject.split("[project]")[1].split("[")[0]
