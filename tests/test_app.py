import shutil
from pathlib import Path
from urllib.parse import quote

from nicegui import ElementFilter, ui
from nicegui.testing import User

from sql_test.engine import Engine
from sql_test.executors import DuckDBExecutor
from sql_test.integrations.app import register_app
from sql_test.integrations.config import RepositoryConfig
from sql_test.testing import run_case

FIXTURE = Path(__file__).parent / "fixtures" / "repos" / "lakehouse-data-customer"
DEMO = Path(__file__).parent / "fixtures" / "repos" / "lineage-demo"

ALICE = "medicaid_members_named_alice"


def _register(repository: Path) -> None:
    register_app(repository, DuckDBExecutor())


def _text(user: User, marker: str) -> str:
    (element,) = user.find(marker=marker).elements
    assert isinstance(element, ui.label | ui.link)
    return element.text


def _count(user: User, marker: str) -> int:
    with user:
        return len(list(ElementFilter(marker=marker)))


def _count_within(user: User, marker: str, *, within: str) -> int:
    with user:
        return len(list(ElementFilter(marker=marker).within(marker=within)))


def _value(user: User, marker: str) -> str:
    (field,) = user.find(kind=ui.input, marker=marker).elements
    return field.value


def _expansion(user: User, marker: str) -> ui.expansion:
    (panel,) = user.find(kind=ui.expansion, marker=marker).elements
    return panel


def _fill(user: User, table: str, rows: list[dict[str, str]]) -> None:
    for index, row in enumerate(rows):
        if index:
            user.find(marker=f"add-row-{table}").click()
        for column, value in row.items():
            user.find(marker=f"cell-{table}.{index}.{column}").type(value)


def _copy_fixture(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    shutil.copytree(FIXTURE, repo)
    return repo


async def test_app_page_lists_models_and_sources(user: User):
    _register(FIXTURE)
    await user.open("/")

    await user.should_see("Tables")
    await user.should_see("Tests")
    await user.should_see("In pipelines")
    await user.should_see(marker="table-medicaid_members")
    await user.should_see(marker=f"table-{ALICE}")
    await user.should_see(marker="table-members")
    await user.should_not_see("Boundaries")


async def test_home_lists_cases_with_their_table(user: User):
    """APP-26: Alice's cases sit with that table, not only a global Cases list."""
    _register(FIXTURE)
    await user.open("/")

    await user.should_see(marker=f"table-{ALICE}")
    alice_case = f"{ALICE}/only_medicaid_alices"
    await user.should_see(marker=f"table-case-{alice_case}")
    assert (
        _count_within(user, f"table-case-{alice_case}", within=f"table-cases-{ALICE}")
        == 1
    )
    await user.should_see(marker=f"table-case-{ALICE}/from_mocked_medicaid_members")


async def test_untested_table_with_pipeline_case_opens_from_the_browser(
    user: User, tmp_path: Path
):
    repo = tmp_path / "repo"
    shutil.copytree(FIXTURE, repo)
    shutil.rmtree(repo / "tests" / "cases" / "medicaid_members")
    case = f"{ALICE}/only_medicaid_alices"

    _register(repo)
    await user.open("/")
    await user.should_see(marker="table-medicaid_members")
    assert _text(user, "tests-medicaid_members") == "0"
    assert _text(user, "pipelines-medicaid_members") == "1"

    user.find(marker="pipelines-medicaid_members").click()
    await user.should_see(marker=f"pipeline-case-{case}")
    user.find(marker=f"pipeline-case-{case}").click()

    await user.should_see("Workbench")
    await user.should_see(marker="case-label", content="only_medicaid_alices")


async def test_selecting_a_model_opens_the_workbench(user: User):
    _register(FIXTURE)
    await user.open("/")
    user.find(marker=f"table-{ALICE}").click()

    await user.should_see("Workbench")
    await user.should_see(marker="target", content=ALICE)
    await user.should_see("table under test")
    await user.should_see(marker="lineage-graph")
    await user.should_see(marker="view-sql")
    await user.should_see(marker="view-lineage")

    user.find(marker="view-sql").click()
    await user.should_see("from medicaid_members")
    await user.should_see(marker="sql-file", content=f"{ALICE}.sql")
    await user.should_see("Alice")


async def test_opening_a_table_lists_its_cases_and_loads_one(user: User):
    """APP-26: workbench for a target lists that table's cases; choosing one loads it."""
    _register(FIXTURE)
    await user.open(f"/workbench?target={ALICE}")

    await user.should_see(marker="target", content=ALICE)
    alice_case = f"{ALICE}/only_medicaid_alices"
    await user.should_see(marker=f"target-case-{alice_case}")
    await user.should_see(marker=f"target-case-{ALICE}/from_mocked_medicaid_members")
    await user.should_not_see(marker="case-label")

    user.find(marker=f"target-case-{alice_case}").click()

    await user.should_see(marker="case-label", content="only_medicaid_alices")
    await user.should_see(marker="grid-members")
    await user.should_see(marker="grid-lob")


async def test_the_app_reads_paths_from_the_repository_config(
    user: User, tmp_path: Path
):
    repo = _copy_fixture(tmp_path)
    (repo / "admin" / "sqls").rename(repo / "sql")
    (repo / "admin" / "config" / "lookup_sql_table_mapping.csv").rename(
        repo / "mapping.csv"
    )
    (repo / "pyproject.toml").write_text(
        "[tool.sql-test]\n"
        'sqls = "sql"\n'
        'mapping = "mapping.csv"\n'
        'schemas = "sql"\n'
        'cases = "tests/cases"\n'
    )

    _register(repo)
    await user.open(f"/workbench?target={ALICE}&view=sql")
    await user.should_see("from medicaid_members")
    user.find(marker="view-lineage").click()
    await user.should_see(marker="node-medicaid_members")


async def test_changing_cases_in_the_app_updates_pyproject_and_lists_the_new_folder(
    user: User, tmp_path: Path
):
    repo = _copy_fixture(tmp_path)
    (repo / "tests" / "cases").rename(repo / "cases_v2")
    before = (
        "# keep me\n"
        "[project]\n"
        'name = "demo"\n'
        "\n"
        "[tool.ruff]\n"
        "line-length = 88\n"
        "\n"
        "[tool.sql-test]\n"
        'sqls = "admin/sqls"\n'
        'mapping = "admin/config/lookup_sql_table_mapping.csv"\n'
        'schemas = "admin/sqls"\n'
        'cases = "tests/cases"\n'
        "\n"
        "# trailing\n"
    )
    (repo / "pyproject.toml").write_text(before)

    _register(repo)
    await user.open("/settings")
    await user.should_see(marker="settings")
    (cases_field,) = user.find(kind=ui.input, marker="path-cases").elements
    cases_field.set_value("cases_v2")
    user.find(marker="save-settings").click()

    await user.should_see(marker="settings-saved")
    after = (repo / "pyproject.toml").read_text()
    assert 'cases = "cases_v2"' in after
    without_cases = lambda text: "\n".join(
        line for line in text.splitlines() if not line.startswith("cases =")
    )
    assert without_cases(before) == without_cases(after)

    await user.open("/")
    await user.should_see(marker=f"table-case-{ALICE}/only_medicaid_alices")


async def test_a_repository_without_config_opens_settings(user: User, tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')

    _register(tmp_path)
    await user.open("/")

    await user.should_see(marker="settings")
    await user.should_see(marker="path-sqls")


async def test_lineage_view_shows_grey_sources_that_need_rows(user: User):
    _register(FIXTURE)
    await user.open(f"/workbench?target={ALICE}&view=lineage")

    await user.should_see("Lineage")
    await user.should_see(marker="lineage-graph")
    await user.should_see(marker="node-members")
    await user.should_see(marker="needs-rows")
    await user.should_see(marker=f"reads-{ALICE}", content="medicaid_members")
    await user.should_not_see("from medicaid_members")


async def test_clicking_medicaid_members_mocks_it_and_prunes_members(user: User):
    _register(FIXTURE)
    await user.open(f"/workbench?target={ALICE}&view=lineage")
    await user.should_see(marker="node-members")
    assert _count(user, "node-mocked") == 0

    user.find(marker="node-medicaid_members").click()
    await user.should_see(marker="node-mocked")
    await user.should_see(marker="node-medicaid_members")
    # members is pruned by the mock — hidden until unmock.
    await user.should_not_see(marker="node-members")
    await user.should_see(marker="grid-medicaid_members")

    user.find(marker="node-medicaid_members").click()
    await user.should_see(marker="node-members")
    await user.should_not_see(marker="node-mocked")
    await user.should_not_see(marker="grid-medicaid_members")


async def test_opening_with_a_mock_in_the_link_marks_it_mocked(user: User):
    _register(FIXTURE)
    await user.open(f"/workbench?target={ALICE}&view=lineage&mock=medicaid_members")

    assert _count(user, "node-mocked") == 1
    await user.should_see(marker="node-medicaid_members")
    await user.should_not_see(marker="node-members")


async def test_demo_tree_hides_pruned_and_keeps_frontier_mocks(user: User):
    _register(DEMO)
    await user.open(
        "/workbench?target=customer_summary&view=lineage&mock=staged_claims"
    )

    await user.should_see(marker="node-mocked")
    await user.should_see("will execute")
    await user.should_see("source")
    await user.should_see(marker="node-staged_claims")
    await user.should_see(marker="node-raw_members")
    await user.should_see(marker="node-customer_summary")
    # raw_claims is pruned by mocking staged_claims — hidden until unmock.
    await user.should_not_see(marker="node-raw_claims")
    await user.should_not_see(marker="node-pruned")
    await user.should_see(marker="plan-blocked")

    # A redundant upstream mock is dropped; still one mocked frontier node.
    await user.open(
        "/workbench?target=customer_summary&mock=staged_claims&mock=raw_claims"
    )
    assert _count(user, "node-mocked") == 1
    await user.should_not_see(marker="node-raw_claims")


async def test_a_mock_another_path_still_reads_is_kept(user: User, tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        "[tool.sql-test]\n"
        'sqls = "sql"\n'
        'mapping = "mapping.csv"\n'
        'schemas = "sql"\n'
        'cases = "cases"\n'
    )
    sql = tmp_path / "sql"
    sql.mkdir()
    (sql / "ddl.sql").write_text(
        "".join(
            f"create table {name} (id int);\n" for name in ("base", "middle", "top")
        )
    )
    (sql / "middle.sql").write_text("select * from base")
    (sql / "top.sql").write_text("select middle.id from middle, base")
    (tmp_path / "mapping.csv").write_text(
        "table_ref,sql_ref\nmiddle,middle.sql\ntop,top.sql\n"
    )

    _register(tmp_path)
    await user.open("/workbench?target=top&mock=middle&mock=base")

    assert _count(user, "node-mocked") == 2


async def test_covering_needs_rows_marks_ready_to_run(user: User):
    _register(DEMO)
    await user.open(
        "/workbench?target=customer_summary&view=lineage"
        "&mock=staged_claims&mock=raw_members"
    )
    await user.should_see(marker="plan-blocked")

    _fill(user, "staged_claims", [{"claim_id": "1", "member_id": "1"}])
    _fill(user, "raw_members", [{"member_id": "1", "member_name": "Ada"}])

    await user.should_see("Ready to run")
    await user.should_not_see("Blocked")


async def test_mocked_table_opens_a_schema_aware_grid(user: User):
    _register(FIXTURE)
    await user.open(f"/workbench?target={ALICE}&view=lineage&mock=members")

    await user.should_see("Mock editor")
    await user.should_see(marker="grid-members")
    await user.should_see("member_id")
    await user.should_see("member_name")
    await user.should_see(marker="cell-members.0.member_id")
    await user.should_see(marker="cell-members.0.member_name")
    await user.should_see(marker="cell-members.0.lob")


async def test_clicking_blocked_needs_rows_focuses_that_grid(user: User):
    """APP-30: blocked status names jump to the matching mock grid."""
    _register(FIXTURE)
    await user.open(f"/workbench?target={ALICE}&view=lineage&mock=members")
    await user.should_see(marker="plan-blocked")
    await user.should_see(marker="grid-members")

    user.find(marker="focus-grid-members").click()

    (cell,) = user.find(kind=ui.input, marker="cell-members.0.member_id").elements
    assert "grid-focus" in cell.classes


async def test_mocking_a_frontier_table_focuses_its_grid(user: User):
    """APP-30: mocking a node lands focus on that table's grid."""
    _register(FIXTURE)
    await user.open(f"/workbench?target={ALICE}&view=lineage")
    await user.should_see(marker="node-members")

    user.find(marker="node-members").click()

    await user.should_see(marker="grid-members")
    (cell,) = user.find(kind=ui.input, marker="cell-members.0.member_id").elements
    assert "grid-focus" in cell.classes


async def test_clicking_a_node_adds_its_grid_without_losing_typed_rows(user: User):
    _register(FIXTURE)
    await user.open(f"/workbench?target={ALICE}&view=lineage&mock=members")
    _fill(user, "members", [{"member_id": "1", "member_name": "Ada", "lob": "30"}])

    user.find(marker="node-lob").click()
    await user.should_see(marker="grid-lob")

    assert _value(user, "cell-members.0.member_name") == "Ada"


async def test_grid_can_add_and_delete_rows(user: User):
    _register(FIXTURE)
    await user.open(f"/workbench?target={ALICE}&view=lineage&mock=members")
    _fill(user, "members", [{"member_id": "1", "member_name": "Ada", "lob": "30"}])

    user.find(marker="add-row-members").click()
    await user.should_see(marker="cell-members.1.member_id")
    user.find(marker="cell-members.1.member_id").type("2")
    user.find(marker="cell-members.1.member_name").type("Bea")
    user.find(marker="cell-members.1.lob").type("10")

    user.find(marker="delete-members.0").click()
    await user.should_not_see(marker="cell-members.1.member_id")
    assert _value(user, "cell-members.0.member_id") == "2"
    assert _value(user, "cell-members.0.member_name") == "Bea"


async def test_tab_from_a_cell_focuses_the_next_cell_not_row_actions(user: User):
    _register(FIXTURE)
    await user.open(f"/workbench?target={ALICE}&view=lineage&mock=members")
    await user.should_see(marker="cell-members.0.member_id")

    (duplicate,) = user.find(marker="duplicate-members.0").elements
    (delete,) = user.find(marker="delete-members.0").elements
    assert str(duplicate.props.get("tabindex")) == "-1"
    assert str(delete.props.get("tabindex")) == "-1"

    user.find(marker="cell-members.0.member_id").trigger("keydown.exact.tab.prevent")

    (next_cell,) = user.find(
        kind=ui.input, marker="cell-members.0.member_name"
    ).elements
    assert "grid-focus" in next_cell.classes


async def test_tab_from_the_last_cell_of_a_row_adds_a_row(user: User):
    _register(FIXTURE)
    await user.open(f"/workbench?target={ALICE}&view=lineage&mock=members")
    await user.should_see(marker="cell-members.0.lob")
    await user.should_not_see(marker="cell-members.1.member_id")

    user.find(marker="cell-members.0.lob").trigger("keydown.exact.tab.prevent")

    await user.should_see(marker="cell-members.1.member_id")
    (first_of_new,) = user.find(
        kind=ui.input, marker="cell-members.1.member_id"
    ).elements
    assert "grid-focus" in first_of_new.classes


async def test_shift_tab_walks_cells_in_reverse_without_row_actions(user: User):
    _register(FIXTURE)
    await user.open(f"/workbench?target={ALICE}&view=lineage&mock=members")
    user.find(marker="add-row-members").click()
    await user.should_see(marker="cell-members.1.member_id")

    (duplicate,) = user.find(marker="duplicate-members.0").elements
    assert str(duplicate.props.get("tabindex")) == "-1"

    user.find(marker="cell-members.1.member_id").trigger("keydown.shift.tab.prevent")

    (previous,) = user.find(kind=ui.input, marker="cell-members.0.lob").elements
    assert "grid-focus" in previous.classes
    await user.should_see(marker="cell-members.1.member_id")


async def test_mock_editor_has_no_synthetic_data_reminder(user: User):
    """UAT-11: drop the compliance reminder entirely."""
    _register(FIXTURE)
    await user.open(f"/workbench?target={ALICE}&view=lineage&mock=members")
    await user.should_see(marker="cell-members.0.member_id")
    assert _count(user, "synthetic-data-reminder") == 0


async def test_pasting_tsv_into_a_cell_fills_several_rows_and_columns(user: User):
    """Paste starts at the focused cell; blanks become NULL."""
    _register(FIXTURE)
    await user.open(f"/workbench?target={ALICE}&view=lineage&mock=members")
    await user.should_see(marker="cell-members.0.member_id")

    user.find(marker="cell-members.0.member_id").trigger(
        "paste",
        args={"text": "1\tAda\t30\n2\t\t10\n"},
    )

    await user.should_see(marker="cell-members.1.member_id")
    assert _value(user, "cell-members.0.member_id") == "1"
    assert _value(user, "cell-members.0.member_name") == "Ada"
    assert _value(user, "cell-members.0.lob") == "30"
    assert _value(user, "cell-members.1.member_id") == "2"
    await user.should_see(marker="null-members.1.member_name")
    assert _value(user, "cell-members.1.lob") == "10"


async def test_a_non_integer_member_id_is_flagged_before_running(user: User):
    _register(FIXTURE)
    await user.open(f"/workbench?target={ALICE}&view=lineage&mock=members")
    user.find(marker="cell-members.0.member_id").type("abc")

    await user.should_see(marker="invalid-members.0.member_id")
    await user.should_see(marker="invalid-members.0.member_id", content="not INT")


async def test_duplicate_row_copies_the_row(user: User):
    _register(FIXTURE)
    await user.open(f"/workbench?target={ALICE}&view=lineage&mock=members")
    _fill(user, "members", [{"member_id": "1", "member_name": "Ada", "lob": "30"}])

    user.find(marker="duplicate-members.0").click()

    await user.should_see(marker="cell-members.1.member_id")
    assert _value(user, "cell-members.1.member_id") == "1"
    assert _value(user, "cell-members.1.member_name") == "Ada"
    assert _value(user, "cell-members.1.lob") == "30"


def _set_null(user: User, marker: str) -> None:
    """APP-28: Ctrl+; sets NULL on the focused cell (no per-cell NULL button)."""
    user.find(marker=marker).trigger("keydown.ctrl.exact.;.prevent")


async def test_members_grid_has_no_per_cell_null_button(user: User):
    """APP-28: values read as a table; NULL chrome is not beside every input."""
    _register(FIXTURE)
    await user.open("/workbench?target=members&view=lineage&mock=members")
    await user.should_see(marker="cell-members.0.member_id")
    await user.should_not_see(marker="null-toggle-members.0.member_id")
    await user.should_not_see(marker="null-toggle-members.0.member_name")
    assert _count(user, "null-toggle-members.0.member_id") == 0
    await user.should_see(marker="null-hint")
    await user.should_see("Ctrl+; sets NULL")


async def test_null_hint_shows_while_editing_expected(user: User):
    """NULL shortcut is documented where Expected is edited, not only in docs."""
    _register(FIXTURE)
    await user.open(f"/workbench?target={ALICE}&view=lineage&mock=members")
    await user.should_see(marker="grid-expected")
    await user.should_see(marker="null-hint")
    await user.should_see("Ctrl+; sets NULL")


async def test_null_is_distinct_from_an_empty_string(user: User):
    _register(FIXTURE)
    await user.open("/workbench?target=members&view=lineage&mock=members")
    user.find(marker="cell-members.0.member_name").type("Ada")

    _set_null(user, "cell-members.0.member_name")
    await user.should_see(marker="null-members.0.member_name")
    assert _value(user, "cell-members.0.member_name") == ""

    _set_null(user, "cell-members.0.member_name")
    await user.should_see(marker="null-members.0.member_name")

    user.find(marker="cell-members.0.member_name").trigger("keydown", args={"key": "x"})
    await user.should_not_see(marker="null-members.0.member_name")
    user.find(marker="cell-members.0.member_name").clear()
    await user.should_not_see(marker="null-members.0.member_name")
    assert _value(user, "cell-members.0.member_name") == ""


async def test_ctrl_semicolon_shows_null_immediately_on_expected(user: User):
    """Expected grid must show the NULL placeholder without waiting for Run."""
    _register(FIXTURE)
    await user.open(f"/workbench?target={ALICE}&view=lineage&mock=members")
    await user.should_see(marker="cell-expected.0.member_id")

    _set_null(user, "cell-expected.0.member_id")

    await user.should_see(marker="null-expected.0.member_id")


async def test_typing_clears_null_without_making_empty_string_null(user: User):
    """NULL → type leaves NULL; clear all text stays empty string; only Ctrl+; sets NULL."""
    _register(FIXTURE)
    await user.open("/workbench?target=members&view=lineage&mock=members")
    user.find(marker="cell-members.0.member_name").type("Ada")
    _set_null(user, "cell-members.0.member_name")
    await user.should_see(marker="null-members.0.member_name")

    user.find(marker="cell-members.0.member_name").trigger("keydown", args={"key": "B"})
    await user.should_not_see(marker="null-members.0.member_name")
    assert _value(user, "cell-members.0.member_name") == "B"

    user.find(marker="cell-members.0.member_name").clear()
    await user.should_not_see(marker="null-members.0.member_name")
    assert _value(user, "cell-members.0.member_name") == ""


async def test_grid_rows_show_engine_types_after_run(user: User):
    _register(FIXTURE)
    await user.open("/workbench?target=members&view=lineage&mock=members")
    row = {"member_id": "1", "member_name": "Ada", "lob": "30"}
    _fill(user, "members", [row])
    _fill(user, "expected", [row])

    user.find(marker="run").click()

    await user.should_see(marker="verdict-passed")
    await user.should_see(marker="grid-members")
    assert _text(user, "engine-type-members.member_id") == "int"
    assert _value(user, "cell-members.0.member_id") == "1"


async def test_run_with_bad_types_shows_an_error_not_a_blank_page(user: User):
    _register(DEMO)
    await user.open(
        "/workbench?target=customer_summary&view=lineage"
        "&mock=staged_claims&mock=staged_members"
    )
    _fill(user, "staged_claims", [{"claim_id": "a", "member_id": "1"}])
    _fill(user, "staged_members", [{"member_id": "1", "member_name": "Ada"}])

    user.find(marker="run").click()

    await user.should_see("Mock editor")
    await user.should_see("Could not run")
    message = _text(user, "status-error")
    assert (
        "claim_id" in message
        or "invalid" in message.lower()
        or "int" in message.lower()
    )
    assert _value(user, "cell-staged_claims.0.claim_id") == "a"


async def test_alice_passes_with_run_only_and_no_apply_peer(user: User):
    """APP-25: Passed via Run/Save only; engine types after Run; Apply is not a peer."""
    _register(FIXTURE)
    await user.open(
        "/workbench?case=" + quote(f"{ALICE}/only_medicaid_alices", safe="")
    )
    await user.should_see(marker="run")
    await user.should_see(marker="save")
    await user.should_not_see(marker="apply")

    user.find(marker="run").click()

    await user.should_see(marker="verdict-passed")
    assert _text(user, "verdict-passed") == "Passed"
    assert _text(user, "engine-type-members.member_id") == "int"


async def test_running_alice_shows_one_row_and_counts_on_the_graph(user: User):
    _register(FIXTURE)
    await user.open(f"/workbench?target={ALICE}&view=lineage&mock=members&mock=lob")
    _fill(
        user,
        "members",
        [
            {"member_id": "1", "member_name": "Alice", "lob": "30"},
            {"member_id": "2", "member_name": "Alice", "lob": "10"},
            {"member_id": "3", "member_name": "Bea", "lob": "30"},
        ],
    )
    _fill(
        user,
        "lob",
        [
            {"lob": "30", "lob_name": "Medicaid"},
            {"lob": "10", "lob_name": "Commercial"},
        ],
    )

    user.find(marker="run").click()

    await user.should_see(marker="result-view-diff")
    await user.should_see(marker="verdict-failed")
    await user.should_see("Failed — add expected rows")
    user.find(marker="result-output").click()
    await user.should_see(marker="output-rows-1")
    await user.should_see("Alice")
    assert _text(user, "rows-members") == "3 rows"
    assert _text(user, "rows-lob") == "2 rows"
    assert _text(user, "rows-medicaid_members") == "2 rows"
    assert _text(user, f"rows-{ALICE}") == "1 rows"


async def test_run_with_matching_expected_shows_passed(user: User):
    _register(FIXTURE)
    await user.open("/workbench?target=members&view=lineage&mock=members")
    row = {"member_id": "1", "member_name": "Ada", "lob": "30"}
    _fill(user, "members", [row])
    _fill(user, "expected", [row])

    user.find(marker="run").click()

    await user.should_see(marker="verdict-passed")
    assert _text(user, "verdict-passed") == "Passed"
    await user.should_see(marker="result-view-output")
    user.find(marker="result-diff").click()
    await user.should_see(marker="diff-clean")


async def test_failed_run_defaults_to_diff_even_when_output_was_requested(user: User):
    _register(FIXTURE)
    await user.open("/workbench?target=members&view=lineage&mock=members")
    row = {"member_id": "1", "member_name": "Ada", "lob": "30"}
    _fill(user, "members", [row])
    _fill(user, "expected", [row])
    user.find(marker="run").click()
    await user.should_see(marker="result-view-output")

    user.find(marker="cell-expected.0.member_name").clear().type("Beatrice")
    user.find(marker="run").click()

    await user.should_see(marker="verdict-failed")
    await user.should_see(marker="result-view-diff")
    await user.should_see(marker="diff-changed")


async def test_diff_shows_changed_missing_and_added_like_git(user: User):
    _register(FIXTURE)
    await user.open("/workbench?target=members&view=lineage&mock=members")
    _fill(
        user,
        "members",
        [
            {"member_id": "1", "member_name": "Ada", "lob": "30"},
            {"member_id": "2", "member_name": "Bea", "lob": "10"},
            {"member_id": "3", "member_name": "Cia", "lob": "30"},
        ],
    )
    _fill(
        user,
        "expected",
        [
            {"member_id": "1", "member_name": "Ada", "lob": "30"},
            {"member_id": "2", "member_name": "Beatrice", "lob": "10"},
            {"member_id": "9", "member_name": "Dia", "lob": "30"},
        ],
    )

    user.find(marker="run").click()

    await user.should_see(marker="result-view-diff")
    assert _text(user, "verdict-failed") == "Failed"
    await user.should_not_see(marker="diff-matching")
    await user.should_see(marker="diff-changed")
    await user.should_see(marker="diff-missing")
    await user.should_see(marker="diff-added")
    await user.should_see("@@ changed @@")
    await user.should_see(marker="diff-removed")
    await user.should_see(marker="diff-added")
    for name in ("Beatrice", "Bea", "Dia", "Cia"):
        await user.should_see(name)
    await user.should_see(marker="cell-expected.0.member_name")


async def _run_a_failing_case(user: User) -> None:
    _register(FIXTURE)
    await user.open("/workbench?target=members&view=lineage&mock=members")
    _fill(
        user,
        "members",
        [
            {"member_id": "1", "member_name": "Ada", "lob": "30"},
            {"member_id": "2", "member_name": "Bea", "lob": "10"},
            {"member_id": "3", "member_name": "Cia", "lob": "30"},
        ],
    )
    _fill(
        user,
        "expected",
        [
            {"member_id": "1", "member_name": "Ada", "lob": "30"},
            {"member_id": "2", "member_name": "Beatrice", "lob": "10"},
            {"member_id": "9", "member_name": "Dia", "lob": "30"},
        ],
    )
    user.find(marker="run").click()
    await user.should_see(marker="verdict-failed")


async def test_accepting_the_whole_actual_result_makes_the_case_pass(user: User):
    await _run_a_failing_case(user)

    user.find(marker="accept-all").click()

    await user.should_see(marker="verdict-passed")
    assert _count(user, "cell-expected.2.member_name") == 1
    assert _value(user, "cell-expected.1.member_name") == "Bea"
    user.find(marker="run").click()
    await user.should_see(marker="verdict-passed")


async def test_workbench_split_keeps_setup_left_and_outcome_right(
    user: User,
):
    """APP-32: after Run, setup (Expected, Run/Save) stays left; outcome right."""
    _register(FIXTURE)
    await user.open(f"/workbench?target={ALICE}&view=lineage&mock=medicaid_members")
    _fill(user, "medicaid_members", [{"member_id": "1", "member_name": "Alice"}])
    _fill(user, "expected", [{"member_id": "1", "member_name": "Wrong"}])

    user.find(marker="run").click()

    await user.should_see(marker="verdict-failed")
    await user.should_see(marker="workbench-setup")
    await user.should_see(marker="workbench-outcome")
    assert _count_within(user, "grid-expected", within="workbench-setup") == 1
    assert (
        _count_within(user, "cell-expected.0.member_name", within="workbench-setup")
        == 1
    )
    assert _count_within(user, "run", within="workbench-setup") == 1
    assert _count_within(user, "save", within="workbench-setup") == 1
    assert _count_within(user, "verdict-failed", within="workbench-outcome") == 1
    assert _count_within(user, "accept-all", within="workbench-outcome") == 1
    assert _count_within(user, "grid-expected", within="workbench-outcome") == 0

    user.find(marker="accept-all").click()

    await user.should_see(marker="verdict-passed")
    assert _count_within(user, "verdict-passed", within="workbench-outcome") == 1
    assert _value(user, "cell-expected.0.member_name") == "Alice"
    assert (
        _count_within(user, "cell-expected.0.member_name", within="workbench-setup")
        == 1
    )
    assert _count_within(user, "run", within="workbench-setup") == 1
    assert _count_within(user, "save", within="workbench-setup") == 1


async def test_mock_and_expected_grids_start_collapsed_and_can_open_together(
    user: User,
):
    """APP-32: grids default collapsed; any combination may be open at once."""
    _register(FIXTURE)
    await user.open(f"/workbench?target={ALICE}&view=lineage&mock=members&mock=lob")

    await user.should_see(marker="grid-expand-members")
    await user.should_see(marker="grid-expand-lob")
    await user.should_see(marker="grid-expand-expected")
    members = _expansion(user, "grid-expand-members")
    lob = _expansion(user, "grid-expand-lob")
    expected = _expansion(user, "grid-expand-expected")
    assert members.value is False
    assert lob.value is False
    assert expected.value is False

    members.set_value(True)
    lob.set_value(True)
    assert _expansion(user, "grid-expand-members").value is True
    assert _expansion(user, "grid-expand-lob").value is True
    assert _expansion(user, "grid-expand-expected").value is False


async def test_jumping_to_a_mock_expands_its_collapsed_grid(user: User):
    """APP-32: focus / jump expands that mock on the setup pane."""
    _register(FIXTURE)
    await user.open(f"/workbench?target={ALICE}&view=lineage&mock=members")
    assert _expansion(user, "grid-expand-members").value is False

    user.find(marker="focus-grid-members").click()

    assert _expansion(user, "grid-expand-members").value is True
    (cell,) = user.find(kind=ui.input, marker="cell-members.0.member_id").elements
    assert "grid-focus" in cell.classes


async def test_a_new_case_run_with_blank_expected_can_accept_its_actual_result(
    user: User,
):
    _register(FIXTURE)
    await user.open("/workbench?target=members&view=lineage&mock=members")
    _fill(
        user,
        "members",
        [
            {"member_id": "1", "member_name": "Ada", "lob": "30"},
            {"member_id": "2", "member_name": "Bea", "lob": "10"},
        ],
    )
    user.find(marker="run").click()

    user.find(marker="accept-all").click()

    await user.should_see(marker="verdict-passed")
    assert _value(user, "cell-expected.1.member_name") == "Bea"


async def test_accepting_empty_actual_asks_before_expecting_no_rows(user: User):
    """UAT-8: Accept all with zero actual rows must not silently set Expects no rows."""
    _register(FIXTURE)
    await user.open(f"/workbench?target={ALICE}&view=lineage&mock=medicaid_members")
    _fill(user, "medicaid_members", [{"member_id": "1", "member_name": "Ada"}])
    user.find(marker="run").click()
    await user.should_see(marker="verdict-failed")
    await user.should_see(marker="diff-empty")

    user.find(marker="accept-all").click()

    await user.should_see(marker="accept-empty-confirm")
    await user.should_not_see(marker="expected-no-rows")
    await user.should_see(marker="verdict-failed")

    user.find(marker="accept-empty-cancel").click()

    await user.should_not_see(marker="expected-no-rows")
    await user.should_see(marker="verdict-failed")

    user.find(marker="accept-all").click()
    user.find(marker="accept-empty-confirm").click()

    await user.should_see(marker="verdict-passed")
    await user.should_see(marker="expected-no-rows")


async def test_accepting_no_rows_expects_no_rows_through_save_and_load(
    user: User, tmp_path: Path
):
    repo = _copy_fixture(tmp_path)
    _register(repo)
    await user.open(f"/workbench?target={ALICE}&view=lineage&mock=medicaid_members")
    _fill(user, "medicaid_members", [{"member_id": "1", "member_name": "Ada"}])
    user.find(marker="run").click()
    await user.should_see(marker="verdict-failed")
    await user.should_see(marker="diff-empty")

    user.find(marker="accept-all").click()
    user.find(marker="accept-empty-confirm").click()

    await user.should_see(marker="verdict-passed")
    await user.should_see(marker="expected-no-rows")
    user.find(marker="case-name").type("no_alice")
    user.find(marker="save").click()
    await user.should_see("Saved case")
    folder = repo / "tests" / "cases" / ALICE / "no_alice"
    assert (folder / "expected.csv").read_text() == "member_id,member_name\n"
    config = RepositoryConfig.load(repo)
    result = run_case(
        folder, Engine(catalog=config.catalog(), executor=DuckDBExecutor())
    )
    assert result.passed, result.report()

    await user.open("/workbench?case=" + quote(f"{ALICE}/no_alice", safe=""))
    await user.should_see(marker="expected-no-rows")
    user.find(marker="run").click()
    await user.should_see(marker="verdict-passed")


async def test_accepting_a_changed_row_replaces_the_expected_row(user: User):
    await _run_a_failing_case(user)

    user.find(marker="accept-row-changed-0").click()

    assert _value(user, "cell-expected.1.member_name") == "Bea"
    await user.should_see(marker="verdict-failed")
    await user.should_not_see(marker="diff-changed")


async def test_accepting_a_changed_cell_takes_the_actual_value(user: User):
    await _run_a_failing_case(user)

    user.find(marker="accept-cell-changed-0-member_name").click()

    assert _value(user, "cell-expected.1.member_name") == "Bea"
    await user.should_not_see(marker="diff-changed")


async def test_accepting_an_added_row_appends_it_to_expected(user: User):
    await _run_a_failing_case(user)

    user.find(marker="accept-row-added-0").click()

    assert _value(user, "cell-expected.3.member_name") == "Cia"
    await user.should_not_see(marker="accept-row-added-0")


async def test_removing_a_missing_row_drops_it_from_expected(user: User):
    await _run_a_failing_case(user)

    user.find(marker="remove-row-missing-0").click()

    assert _count(user, "cell-expected.2.member_name") == 0
    await user.should_not_see(marker="diff-missing")


def _sqls(repo: Path) -> Path:
    return repo / "admin" / "sqls"


def _map(repo: Path, table: str) -> None:
    mapping = repo / "admin" / "config" / "lookup_sql_table_mapping.csv"
    with mapping.open("a") as file:
        file.write(f"historic,{table},{table}.sql\n")


async def test_home_shows_a_newly_mapped_sql_on_the_next_load(
    user: User, tmp_path: Path
):
    repo = _copy_fixture(tmp_path)
    _register(repo)
    await user.open("/")
    await user.should_not_see(marker="table-medicaid_adas")

    (_sqls(repo) / "medicaid_adas.sql").write_text(
        "select member_id, member_name\nfrom medicaid_members\n"
        "where member_name = 'Ada'\n"
    )
    _map(repo, "medicaid_adas")
    await user.open("/")

    await user.should_see(marker="table-medicaid_adas")


async def test_home_drops_a_deleted_mapped_sql_on_the_next_load(
    user: User, tmp_path: Path
):
    repo = _copy_fixture(tmp_path)
    (_sqls(repo) / "medicaid_adas.sql").write_text(
        "select member_id, member_name from medicaid_members\n"
    )
    _map(repo, "medicaid_adas")
    _register(repo)
    await user.open("/")
    await user.should_see(marker="table-medicaid_adas")

    (_sqls(repo) / "medicaid_adas.sql").unlink()
    await user.open("/")

    await user.should_not_see(marker="table-medicaid_adas")
    await user.should_see(marker=f"table-{ALICE}")


async def test_lineage_follows_a_sql_edited_while_the_workbench_is_open(
    user: User, tmp_path: Path
):
    repo = _copy_fixture(tmp_path)
    _register(repo)
    await user.open(f"/workbench?target={ALICE}&view=lineage")
    await user.should_see(marker="node-medicaid_members")

    (_sqls(repo) / f"{ALICE}.sql").write_text(
        "select member_id, member_name\nfrom members\nwhere member_name = 'Alice'\n"
    )
    user.find(marker="view-lineage").click()

    await user.should_not_see(marker="node-medicaid_members")
    await user.should_see(marker="node-members")


async def test_lineage_follows_a_sql_deleted_while_the_workbench_is_open(
    user: User, tmp_path: Path
):
    repo = _copy_fixture(tmp_path)
    _register(repo)
    await user.open(f"/workbench?target={ALICE}&view=lineage")
    await user.should_see(marker="node-members")

    (_sqls(repo) / "medicaid_members.sql").unlink()
    user.find(marker="view-lineage").click()

    await user.should_see(marker="node-medicaid_members")
    await user.should_not_see(marker="node-members")


async def test_run_uses_a_sql_edited_while_the_workbench_is_open(
    user: User, tmp_path: Path
):
    repo = _copy_fixture(tmp_path)
    _register(repo)
    await user.open(f"/workbench?target={ALICE}&view=lineage&mock=medicaid_members")
    _fill(user, "medicaid_members", [{"member_id": "1", "member_name": "Alice"}])
    user.find(marker="run").click()
    user.find(marker="result-output").click()
    await user.should_see(marker="output-rows-1")

    (_sqls(repo) / f"{ALICE}.sql").write_text(
        "select member_id, member_name\nfrom medicaid_members\n"
        "where member_name = 'Bob'\n"
    )
    user.find(marker="run").click()
    user.find(marker="result-output").click()

    await user.should_see(marker="output-rows-0")


async def test_selecting_a_case_opens_the_workbench(user: User, tmp_path: Path):
    case = tmp_path / "cases" / "medicaid_members" / "alice"
    case.mkdir(parents=True)
    (case / "members.csv").write_text("member_id\n1\n")
    (tmp_path / "pyproject.toml").write_text(
        "[tool.sql-test]\n"
        'sqls = "admin/sqls"\n'
        'mapping = "admin/config/lookup_sql_table_mapping.csv"\n'
        'schemas = "admin/sqls"\n'
        'cases = "cases"\n'
    )
    (tmp_path / "admin" / "sqls").mkdir(parents=True)
    (tmp_path / "admin" / "config").mkdir(parents=True)
    (tmp_path / "admin" / "sqls" / "m.sql").write_text("select 1 as member_id")
    (tmp_path / "admin" / "config" / "lookup_sql_table_mapping.csv").write_text(
        "load_type,table_ref,sql_ref\nhistoric,medicaid_members,m.sql\n"
    )

    _register(tmp_path)
    await user.open("/")
    user.find(marker="table-case-medicaid_members/alice").click()

    await user.should_see("Workbench")
    await user.should_see(marker="target", content="medicaid_members")
    await user.should_see(marker="case-label", content="alice")


async def test_opening_a_case_loads_mocks_grids_and_expected(user: User):
    _register(FIXTURE)
    await user.open(
        "/workbench?case=" + quote("medicaid_members/only_medicaid_members", safe="")
    )

    await user.should_see(marker="case-label", content="only_medicaid_members")
    await user.should_see(marker="node-members")
    await user.should_see(marker="node-lob")
    assert _count(user, "node-mocked") == 2
    await user.should_see(marker="grid-members")
    assert _value(user, "cell-members.0.member_name") == "Ada"
    assert _value(user, "cell-members.1.member_name") == "Bea"
    await user.should_see(marker="grid-lob")
    assert _value(user, "cell-lob.0.lob_name") == "Medicaid"
    await user.should_see(marker="grid-expected")
    assert _value(user, "cell-expected.0.member_name") == "Ada"
    assert _value(user, "cell-expected.0.member_id") == "1"


async def test_an_unknown_link_says_not_found(user: User):
    _register(FIXTURE)
    await user.open("/workbench?target=no_such_table")
    await user.should_see(marker="not-found")


async def test_saving_a_loaded_case_writes_identical_files(user: User, tmp_path: Path):
    repo = _copy_fixture(tmp_path)
    case_dir = repo / "tests" / "cases" / "medicaid_members" / "only_medicaid_members"
    before = {path.name: path.read_text() for path in sorted(case_dir.glob("*.csv"))}

    _register(repo)
    await user.open(
        "/workbench?case=" + quote("medicaid_members/only_medicaid_members", safe="")
    )
    user.find(marker="save").click()
    await user.should_see(marker="save-overwrite-confirm")
    user.find(marker="save-overwrite-confirm").click()

    await user.should_see("Saved case")
    await user.should_see(marker="status-detail", content=str(case_dir))
    after = {path.name: path.read_text() for path in sorted(case_dir.glob("*.csv"))}
    assert after == before


async def test_saving_over_an_existing_case_asks_before_replacing_mocks(
    user: User, tmp_path: Path
):
    """UAT-9: overwrite must confirm; cancel keeps prior mock CSVs."""
    repo = _copy_fixture(tmp_path)
    case_dir = repo / "tests" / "cases" / "medicaid_members" / "only_medicaid_members"
    before = {path.name: path.read_text() for path in sorted(case_dir.glob("*.csv"))}

    _register(repo)
    await user.open("/workbench?target=medicaid_members&view=lineage&mock=members")
    _fill(
        user,
        "members",
        [{"member_id": "9", "member_name": "Zed", "lob": "30"}],
    )
    _fill(user, "expected", [{"member_id": "9", "member_name": "Zed"}])
    user.find(marker="case-name").type("only_medicaid_members")

    user.find(marker="save").click()

    await user.should_see(marker="save-overwrite-confirm")
    assert before == {
        path.name: path.read_text() for path in sorted(case_dir.glob("*.csv"))
    }

    user.find(marker="save-overwrite-cancel").click()

    assert before == {
        path.name: path.read_text() for path in sorted(case_dir.glob("*.csv"))
    }
    await user.should_not_see(marker="saved")

    user.find(marker="save").click()
    user.find(marker="save-overwrite-confirm").click()

    await user.should_see("Saved case")
    after = {path.name for path in case_dir.glob("*.csv")}
    assert "members.csv" in after
    assert "lob.csv" not in after
    assert (case_dir / "members.csv").read_text().startswith("member_id")


async def test_case_saved_from_the_page_passes_without_the_app(
    user: User, tmp_path: Path
):
    repo = _copy_fixture(tmp_path)
    _register(repo)
    await user.open(
        "/workbench?target=medicaid_members&view=lineage&mock=members&mock=lob"
    )
    _fill(
        user,
        "members",
        [
            {"member_id": "1", "member_name": "Ada", "lob": "30"},
            {"member_id": "2", "member_name": "Bea", "lob": "10"},
        ],
    )
    _fill(
        user,
        "lob",
        [
            {"lob": "30", "lob_name": "Medicaid"},
            {"lob": "10", "lob_name": "Commercial"},
        ],
    )
    _fill(user, "expected", [{"member_id": "1", "member_name": "Ada"}])
    user.find(marker="case-name").type("from_the_app")

    user.find(marker="save").click()

    await user.should_see("Saved case")
    await user.should_see("medicaid_members/from_the_app")
    await user.should_see(marker="case-label", content="from_the_app")
    folder = repo / "tests" / "cases" / "medicaid_members" / "from_the_app"
    assert folder.is_dir()
    config = RepositoryConfig.load(repo)
    result = run_case(
        folder, Engine(catalog=config.catalog(), executor=DuckDBExecutor())
    )
    assert result.passed, result.report()


async def test_saving_without_a_case_name_is_refused(user: User, tmp_path: Path):
    repo = _copy_fixture(tmp_path)
    _register(repo)
    await user.open("/workbench?target=medicaid_members&mock=members&mock=lob")

    user.find(marker="save").click()

    await user.should_see("Could not save")
    assert "case name is required" in _text(user, "status-error")


async def test_saving_without_a_case_name_points_at_the_case_name_field(
    user: User, tmp_path: Path
):
    """UAT-17: nameless Save must focus/highlight Case name, not only status text."""
    repo = _copy_fixture(tmp_path)
    _register(repo)
    await user.open("/workbench?target=medicaid_members&mock=members&mock=lob")

    user.find(marker="save").click()

    await user.should_see(marker="case-name-needed")
    (field,) = user.find(kind=ui.input, marker="case-name-needed").elements
    assert "case-name-needed" in field.classes
    await user.should_see(marker="status-detail")
    assert "Case name" in _text(user, "status-detail")
