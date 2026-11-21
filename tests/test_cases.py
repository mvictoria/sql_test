from decimal import Decimal
from pathlib import Path

import pytest

from sql_test.engine.catalog.adapters import mapped_sql_folder
from sql_test.engine.relation import Relation
from sql_test.engine.schema import Column
from sql_test.testing.cases import UncastableCell, read_case, write_case

REPOSITORY = Path(__file__).parent / "fixtures" / "repos" / "lakehouse-data-customer"


def _schemas():
    return mapped_sql_folder(
        sqls=REPOSITORY / "admin" / "sqls",
        mapping=REPOSITORY / "admin" / "config" / "lookup_sql_table_mapping.csv",
    ).schemas


def _case_folder(root: Path, files: dict[str, str]) -> Path:
    folder = root / "cases" / "medicaid_members" / "ada_is_medicaid"
    folder.mkdir(parents=True)
    for name, text in files.items():
        (folder / name).write_text(text)
    return folder


def test_reads_mocks_and_expected_as_typed_rows(tmp_path: Path):
    folder = _case_folder(
        tmp_path,
        {
            "members.csv": 'member_id,member_name,lob\n1,Ada,30\n2,,""\n',
            "lob.csv": "lob,lob_name\n30,Medicaid\n",
            "expected.csv": "member_id\n1\n",
        },
    )

    case = read_case(folder, _schemas())

    assert case.target == Relation(name="medicaid_members")
    assert case.name == "ada_is_medicaid"
    assert case.mocks[Relation(name="members")].rows == [
        {"member_id": 1, "member_name": "Ada", "lob": "30"},
        {"member_id": 2, "member_name": None, "lob": ""},
    ]
    assert case.mocks[Relation(name="lob")].columns == ("lob", "lob_name")
    assert case.expected is not None
    assert case.expected.columns == ("member_id",)
    assert case.expected.rows == [{"member_id": 1}]


def test_a_mock_without_a_schema_keeps_its_text(tmp_path: Path):
    folder = _case_folder(tmp_path, {"claims.csv": "claim_id\n7\n"})

    case = read_case(folder, _schemas())

    assert case.mocks[Relation(name="claims")].rows == [{"claim_id": "7"}]
    assert case.expected is None


def test_a_cell_that_cannot_be_cast_is_named(tmp_path: Path):
    folder = _case_folder(
        tmp_path, {"expected.csv": "member_id,member_name\n1,Ada\none,Bea\n"}
    )

    with pytest.raises(UncastableCell, match=r"expected\.csv line 3 member_id"):
        read_case(folder, _schemas())


def test_writing_a_case_back_reproduces_its_files(tmp_path: Path):
    files = {
        "members.csv": 'member_id,member_name,lob\n1,"Ada, Lovelace",30\n2,,""\n',
        "lob.csv": "lob,lob_name\n",
        "expected.csv": 'member_id,member_name\n1,"Ada, Lovelace"\n',
    }
    folder = _case_folder(tmp_path, files)
    copy = tmp_path / "copy"

    write_case(copy, read_case(folder, _schemas()))

    assert {path.name: path.read_text() for path in copy.iterdir()} == files


@pytest.mark.parametrize(
    ("type", "text", "value"),
    [
        ("INT", "1", 1),
        ("DECIMAL(10, 2)", "1.50", Decimal("1.50")),
        ("DOUBLE", "1.5", 1.5),
        ("BOOLEAN", "true", True),
        ("VARCHAR(2)", "30", "30"),
        ("INT", None, None),
    ],
)
def test_a_column_casts_text_to_its_type(type: str, text: str | None, value):
    assert Column(name="c", type=type).cast(text) == value
