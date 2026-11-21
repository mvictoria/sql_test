import shutil
from pathlib import Path

import pytest

pytest_plugins = ["pytester"]

REPOSITORY = Path(__file__).parent / "fixtures" / "repos" / "lakehouse-data-customer"


def _case(root: Path, target: str, name: str, files: dict[str, str]) -> None:
    folder = root / "cases" / target / name
    folder.mkdir(parents=True)
    for file, text in files.items():
        (folder / file).write_text(text)


def test_runs_one_test_per_case_folder(pytester: pytest.Pytester):
    shutil.copytree(REPOSITORY / "admin", pytester.path / "admin")
    mocks = {
        "members.csv": "member_id,member_name,lob\n1,Ada,30\n",
        "lob.csv": "lob,lob_name\n30,Medicaid\n",
    }
    _case(
        pytester.path,
        "medicaid_members",
        "ada_is_medicaid",
        mocks | {"expected.csv": "member_id,member_name\n1,Ada\n"},
    )
    _case(
        pytester.path,
        "medicaid_members",
        "wrong_expectation",
        mocks | {"expected.csv": "member_id,member_name\n2,Bea\n"},
    )

    result = pytester.runpytest("-v")

    result.assert_outcomes(passed=1, failed=1)
    result.stdout.fnmatch_lines(
        [
            "*medicaid_members/ada_is_medicaid PASSED*",
            "*medicaid_members/wrong_expectation FAILED*",
        ]
    )
    result.stdout.fnmatch_lines(["*missing: {'member_id': 2, 'member_name': 'Bea'}*"])
