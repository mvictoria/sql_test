from pathlib import Path

from sql_test.integrations.discover import discover
from sql_test.testing.coverage import case_counts

FIXTURE = Path(__file__).parent / "fixtures" / "repos" / "lakehouse-data-customer"


def test_each_table_reports_its_number_of_cases_including_zero():
    result = discover(FIXTURE)
    tables = (*result.models, *result.sources)

    counts = case_counts(tables, result.cases)

    assert counts["medicaid_members"] == 1
    assert counts["medicaid_members_named_alice"] == 2
    assert counts["members"] == 0
    assert counts["lob"] == 0
    assert set(counts) == set(tables)
