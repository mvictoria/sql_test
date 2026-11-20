from pathlib import Path

from sql_test.engine import Engine

REPOSITORY = Path(__file__).parent / "fixtures" / "repos" / "lakehouse-data-customer"


def test_runs_a_tables_sql_over_given_rows():
    engine = Engine(
        sqls=REPOSITORY / "admin" / "sqls",
        mapping=REPOSITORY / "admin" / "config" / "lookup_sql_table_mapping.csv",
    )

    rows = engine.run(
        "medicaid_members",
        rows={
            "members": [
                {"member_id": 1, "member_name": "Ada", "lob": "30"},
                {"member_id": 2, "member_name": "Bea", "lob": "10"},
            ],
            "lob": [
                {"lob": "30", "lob_name": "Medicaid"},
                {"lob": "10", "lob_name": "Commercial"},
            ],
        },
    )

    assert rows == [(1, "Ada")]
