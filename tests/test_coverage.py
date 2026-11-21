from pathlib import Path

from sql_test.integrations.config import RepositoryConfig
from sql_test.integrations.discover import discover
from sql_test.testing.coverage import case_counts, pipeline_counts

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


def test_with_only_the_alice_case_medicaid_members_is_in_one_pipeline():
    result = discover(FIXTURE)
    tables = (*result.models, *result.sources)
    alice = tuple(case for case in result.cases if case.name == "only_medicaid_alices")
    catalog = RepositoryConfig.load(FIXTURE).catalog()

    assert case_counts(tables, alice)["medicaid_members"] == 0
    assert pipeline_counts(tables, alice, catalog)["medicaid_members"] == 1
    assert pipeline_counts(tables, alice, catalog)["members"] == 0
    assert pipeline_counts(tables, alice, catalog)["lob"] == 0
