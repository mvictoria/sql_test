from pathlib import Path

from sql_test.integrations.discover import discover

FIXTURE = Path(__file__).parent / "fixtures" / "repos" / "lakehouse-data-customer"


def test_discover_lists_models_and_members_source():
    result = discover(FIXTURE)

    assert "medicaid_members" in result.models
    assert "medicaid_members_named_alice" in result.models
    assert "members" in result.sources


def test_discover_lists_case_folders(tmp_path):
    case = tmp_path / "cases" / "medicaid_members" / "alice"
    case.mkdir(parents=True)
    (case / "members.csv").write_text("member_id\n1\n")
    (case / "expected.csv").write_text("member_id\n1\n")
    (tmp_path / "admin" / "sqls").mkdir(parents=True)
    (tmp_path / "admin" / "config").mkdir(parents=True)
    (tmp_path / "admin" / "sqls" / "m.sql").write_text("select 1 as member_id")
    (tmp_path / "admin" / "config" / "lookup_sql_table_mapping.csv").write_text(
        "load_type,table_ref,sql_ref\nhistoric,medicaid_members,m.sql\n"
    )

    result = discover(tmp_path)

    assert len(result.cases) == 1
    assert result.cases[0].target == "medicaid_members"
    assert result.cases[0].name == "alice"
    assert result.cases[0].mocks == ("members",)
    assert result.cases[0].has_expected
