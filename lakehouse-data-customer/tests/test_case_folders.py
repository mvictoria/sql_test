from pathlib import Path

import pytest

from sql_test.testing.cases import case_folders, case_id
from sql_test.testing.run import run_case

CASES = Path(__file__).parent / "cases"


@pytest.mark.parametrize("case", case_folders(CASES), ids=case_id)
def test_case(case, engine):
    result = run_case(case, engine)
    assert result.passed, result.report()
