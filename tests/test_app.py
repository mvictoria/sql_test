import shutil
import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, urlencode

from sql_test.engine import Engine
from sql_test.executors.duckdb import DuckDBExecutor
from sql_test.integrations.app import create_server
from sql_test.integrations.config import RepositoryConfig
from sql_test.testing.run import run_case

FIXTURE = Path(__file__).parent / "fixtures" / "repos" / "lakehouse-data-customer"
DEMO = Path(__file__).parent / "fixtures" / "repos" / "lineage-demo"


def _get(server: ThreadingHTTPServer, path: str) -> str:
    host, port = server.server_address[:2]
    assert isinstance(host, str)
    assert isinstance(port, int)
    connection = HTTPConnection(host, port, timeout=5)
    connection.request("GET", path)
    body = connection.getresponse().read().decode()
    connection.close()
    return body


def _post(
    server: ThreadingHTTPServer,
    path: str,
    fields: dict[str, str] | list[tuple[str, str]],
) -> str:
    host, port = server.server_address[:2]
    assert isinstance(host, str)
    assert isinstance(port, int)
    body = urlencode(fields)
    connection = HTTPConnection(host, port, timeout=5)
    connection.request(
        "POST",
        path,
        body=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    response = connection.getresponse().read().decode()
    connection.close()
    return response


def _with_server(repository: Path):
    server = create_server(repository, host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_app_page_lists_models_and_sources():
    server = _with_server(FIXTURE)
    try:
        body = _get(server, "/")
    finally:
        server.shutdown()
        server.server_close()

    assert "medicaid_members" in body
    assert "medicaid_members_named_alice" in body
    assert "members" in body
    assert "Sources" in body
    assert "Boundaries" not in body


def test_selecting_a_model_opens_the_workbench():
    server = _with_server(FIXTURE)
    try:
        home = _get(server, "/")
        assert 'href="/workbench?target=medicaid_members_named_alice"' in home
        body = _get(server, "/workbench?target=medicaid_members_named_alice")
        sql = _get(server, "/workbench?target=medicaid_members_named_alice&view=sql")
    finally:
        server.shutdown()
        server.server_close()

    assert "Workbench" in body
    assert "medicaid_members_named_alice" in body
    assert "table under test" in body.lower()
    assert 'aria-label="Upstream lineage graph"' in body
    assert "view=sql" in body
    assert "view=lineage" in body
    assert "from medicaid_members" in sql
    assert "medicaid_members_named_alice.sql" in sql
    assert "Alice" in sql


def test_the_app_reads_paths_from_the_repository_config(tmp_path):
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
    server = _with_server(repo)
    try:
        sql = _get(server, "/workbench?target=medicaid_members_named_alice&view=sql")
        lineage = _get(
            server, "/workbench?target=medicaid_members_named_alice&view=lineage"
        )
    finally:
        server.shutdown()
        server.server_close()

    assert "from medicaid_members" in sql
    assert ">medicaid_members</text>" in lineage


def test_lineage_view_shows_grey_sources_that_need_rows():
    server = _with_server(FIXTURE)
    try:
        body = _get(
            server,
            "/workbench?target=medicaid_members_named_alice&view=lineage",
        )
    finally:
        server.shutdown()
        server.server_close()

    assert "Lineage" in body
    assert 'aria-label="Upstream lineage graph"' in body
    assert "<svg" in body
    assert 'class="edge"' in body
    assert "members" in body
    assert "needs-rows" in body
    assert "from medicaid_members" not in body


def test_clicking_medicaid_members_mocks_it_and_prunes_members():
    server = _with_server(FIXTURE)
    try:
        open_graph = _get(
            server,
            "/workbench?target=medicaid_members_named_alice&view=lineage",
        )
        mocked = _get(
            server,
            "/workbench?target=medicaid_members_named_alice&view=lineage"
            "&mock=medicaid_members",
        )
    finally:
        server.shutdown()
        server.server_close()

    assert (
        'href="/workbench?target=medicaid_members_named_alice'
        '&amp;view=lineage&amp;mock=medicaid_members"'
    ) in open_graph
    assert "node mocked" in mocked
    assert ">medicaid_members</text>" in mocked
    # members is pruned by the mock — hidden until unmock.
    assert ">members</text>" not in mocked
    assert (
        'href="/workbench?target=medicaid_members_named_alice&amp;view=lineage"'
        in mocked
    )


def test_demo_tree_hides_pruned_and_keeps_frontier_mocks():
    server = _with_server(DEMO)
    try:
        body = _get(
            server,
            "/workbench?target=customer_summary&view=lineage&mock=staged_claims",
        )
        both = _get(
            server,
            "/workbench?target=customer_summary&mock=staged_claims&mock=raw_claims",
        )
    finally:
        server.shutdown()
        server.server_close()

    assert "mocked" in body
    assert "will execute" in body
    assert "source" in body
    assert "staged_claims" in body
    assert "raw_members" in body
    assert "customer_summary" in body
    # raw_claims is pruned by mocking staged_claims — hidden until unmock.
    assert "raw_claims" not in body
    assert "pruned" not in body or "pruned hidden" in body
    # Redundant upstream mock is dropped; still one mocked frontier node.
    assert both.count("node mocked") == 1
    assert "raw_claims" not in both
    assert "Blocked" in body
    assert "raw_members" in body


def test_a_mock_another_path_still_reads_is_kept(tmp_path):
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
    server = _with_server(tmp_path)
    try:
        body = _get(server, "/workbench?target=top&mock=middle&mock=base")
    finally:
        server.shutdown()
        server.server_close()

    assert body.count("node mocked") == 2


def test_covering_needs_rows_marks_ready_to_run():
    server = _with_server(DEMO)
    try:
        body = _post(
            server,
            "/workbench",
            [
                ("target", "customer_summary"),
                ("view", "lineage"),
                ("mock", "staged_claims"),
                ("mock", "raw_members"),
                ("staged_claims.0.claim_id", "1"),
                ("staged_claims.0.member_id", "1"),
                ("raw_members.0.member_id", "1"),
                ("raw_members.0.member_name", "Ada"),
            ],
        )
    finally:
        server.shutdown()
        server.server_close()

    assert "Ready to run" in body
    assert "Blocked" not in body


def test_mocked_table_opens_a_schema_aware_grid():
    server = _with_server(FIXTURE)
    try:
        body = _get(
            server,
            "/workbench?target=medicaid_members_named_alice&view=lineage&mock=members",
        )
    finally:
        server.shutdown()
        server.server_close()

    assert "Mock editor" in body
    assert 'data-table="members"' in body
    assert "member_id" in body
    assert "member_name" in body
    assert 'name="members.0.member_id"' in body
    assert 'name="members.0.member_name"' in body
    assert 'name="members.0.lob"' in body


def test_grid_can_add_and_delete_rows():
    server = _with_server(FIXTURE)
    try:
        added = _post(
            server,
            "/workbench",
            {
                "target": "medicaid_members_named_alice",
                "view": "lineage",
                "mock": "members",
                "action": "add:members",
                "members.0.member_id": "1",
                "members.0.member_name": "Ada",
                "members.0.lob": "30",
            },
        )
        deleted = _post(
            server,
            "/workbench",
            {
                "target": "medicaid_members_named_alice",
                "view": "lineage",
                "mock": "members",
                "action": "delete:members:0",
                "members.0.member_id": "1",
                "members.0.member_name": "Ada",
                "members.0.lob": "30",
                "members.1.member_id": "2",
                "members.1.member_name": "Bea",
                "members.1.lob": "10",
            },
        )
    finally:
        server.shutdown()
        server.server_close()

    assert 'name="members.1.member_id"' in added
    assert 'name="members.1.member_id"' not in deleted
    assert 'value="2"' in deleted
    assert 'value="Bea"' in deleted


def test_grid_rows_reach_the_engine_with_schema_types():
    server = _with_server(FIXTURE)
    try:
        body = _post(
            server,
            "/workbench",
            {
                "target": "members",
                "view": "lineage",
                "mock": "members",
                "action": "apply",
                "members.0.member_id": "1",
                "members.0.member_name": "Ada",
                "members.0.lob": "30",
            },
        )
    finally:
        server.shutdown()
        server.server_close()

    assert 'data-table="members"' in body
    assert 'data-engine-type="int"' in body
    assert 'name="members.0.member_id" value="1"' in body
    assert "Reached engine" in body


def test_apply_with_bad_types_shows_an_error_not_a_blank_page():
    server = _with_server(DEMO)
    try:
        body = _post(
            server,
            "/workbench",
            [
                ("target", "customer_summary"),
                ("view", "lineage"),
                ("mock", "staged_claims"),
                ("mock", "staged_members"),
                ("action", "apply"),
                ("staged_claims.0.claim_id", "a"),
                ("staged_claims.0.member_id", "1"),
                ("staged_members.0.member_id", "1"),
                ("staged_members.0.member_name", "Ada"),
            ],
        )
    finally:
        server.shutdown()
        server.server_close()

    assert "Mock editor" in body
    assert "Could not load mocks" in body
    assert "Conversion Error" in body or "INT" in body
    assert 'value="a"' in body


def test_running_alice_shows_one_row_and_counts_on_the_graph():
    server = _with_server(FIXTURE)
    try:
        body = _post(
            server,
            "/workbench",
            [
                ("target", "medicaid_members_named_alice"),
                ("view", "lineage"),
                ("mock", "members"),
                ("mock", "lob"),
                ("action", "run"),
                ("members.0.member_id", "1"),
                ("members.0.member_name", "Alice"),
                ("members.0.lob", "30"),
                ("members.1.member_id", "2"),
                ("members.1.member_name", "Alice"),
                ("members.1.lob", "10"),
                ("members.2.member_id", "3"),
                ("members.2.member_name", "Bea"),
                ("members.2.lob", "30"),
                ("lob.0.lob", "30"),
                ("lob.0.lob_name", "Medicaid"),
                ("lob.1.lob", "10"),
                ("lob.1.lob_name", "Commercial"),
            ],
        )
    finally:
        server.shutdown()
        server.server_close()

    assert 'data-result-view="output"' in body
    assert "<h2>Output</h2>" in body
    assert 'data-output-rows="1"' in body
    assert "Alice" in body
    assert 'data-row-count="3" data-relation="members"' in body
    assert 'data-row-count="2" data-relation="lob"' in body
    assert 'data-row-count="2" data-relation="medicaid_members"' in body
    assert 'data-row-count="1" data-relation="medicaid_members_named_alice"' in body


def test_diff_shows_changed_missing_and_added_like_git():
    server = _with_server(FIXTURE)
    try:
        body = _post(
            server,
            "/workbench",
            [
                ("target", "members"),
                ("view", "lineage"),
                ("mock", "members"),
                ("result_view", "diff"),
                ("action", "run"),
                ("members.0.member_id", "1"),
                ("members.0.member_name", "Ada"),
                ("members.0.lob", "30"),
                ("members.1.member_id", "2"),
                ("members.1.member_name", "Bea"),
                ("members.1.lob", "10"),
                ("members.2.member_id", "3"),
                ("members.2.member_name", "Cia"),
                ("members.2.lob", "30"),
                ("expected.0.member_id", "1"),
                ("expected.0.member_name", "Ada"),
                ("expected.0.lob", "30"),
                ("expected.1.member_id", "2"),
                ("expected.1.member_name", "Beatrice"),
                ("expected.1.lob", "10"),
                ("expected.2.member_id", "9"),
                ("expected.2.member_name", "Dia"),
                ("expected.2.lob", "30"),
            ],
        )
    finally:
        server.shutdown()
        server.server_close()

    assert 'data-result-view="diff"' in body
    assert "<h2>Diff</h2>" in body
    assert 'data-outcome="matching"' not in body
    assert 'data-outcome="changed"' in body
    assert 'data-outcome="missing"' in body
    assert 'data-outcome="added"' in body
    assert "@@ changed @@" in body
    assert 'class="diff-removed"' in body
    assert 'class="diff-added"' in body
    assert "Beatrice" in body
    assert "Bea" in body
    assert "Dia" in body
    assert "Cia" in body
    assert 'name="expected.0.member_name"' in body


def test_selecting_a_case_opens_the_workbench(tmp_path):
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

    server = _with_server(tmp_path)
    try:
        home = _get(server, "/")
        href = f"/workbench?case={quote('medicaid_members/alice', safe='')}"
        assert href in home
        body = _get(server, href)
    finally:
        server.shutdown()
        server.server_close()

    assert "Workbench" in body
    assert "medicaid_members" in body
    assert "alice" in body


def test_opening_a_case_loads_mocks_grids_and_expected():
    server = _with_server(FIXTURE)
    try:
        body = _get(
            server,
            "/workbench?case="
            + quote("medicaid_members/only_medicaid_members", safe=""),
        )
    finally:
        server.shutdown()
        server.server_close()

    assert "only_medicaid_members" in body
    assert 'data-relation="members"' in body or 'class="node mocked' in body
    assert ">members</text>" in body
    assert ">lob</text>" in body
    assert 'data-table="members"' in body
    assert 'name="members.0.member_name" value="Ada"' in body
    assert 'name="members.1.member_name" value="Bea"' in body
    assert 'data-table="lob"' in body
    assert 'name="lob.0.lob_name" value="Medicaid"' in body
    assert 'data-table="expected"' in body
    assert 'name="expected.0.member_name" value="Ada"' in body
    assert 'name="expected.0.member_id" value="1"' in body


def _copy_fixture(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    shutil.copytree(FIXTURE, repo)
    return repo


def _medicaid_only_fields(
    case: str | None = "only_medicaid_members",
) -> list[tuple[str, str]]:
    fields: list[tuple[str, str]] = [
        ("view", "lineage"),
        ("mock", "members"),
        ("mock", "lob"),
        ("members.0.member_id", "1"),
        ("members.0.member_name", "Ada"),
        ("members.0.lob", "30"),
        ("members.1.member_id", "2"),
        ("members.1.member_name", "Bea"),
        ("members.1.lob", "10"),
        ("lob.0.lob", "30"),
        ("lob.0.lob_name", "Medicaid"),
        ("lob.1.lob", "10"),
        ("lob.1.lob_name", "Commercial"),
        ("expected.0.member_id", "1"),
        ("expected.0.member_name", "Ada"),
    ]
    if case is not None:
        fields.insert(0, ("case", f"medicaid_members/{case}"))
    else:
        fields.insert(0, ("target", "medicaid_members"))
    return fields


def test_saving_a_loaded_case_writes_identical_files(tmp_path):
    repo = _copy_fixture(tmp_path)
    case_dir = repo / "tests" / "cases" / "medicaid_members" / "only_medicaid_members"
    before = {path.name: path.read_text() for path in sorted(case_dir.glob("*.csv"))}

    server = _with_server(repo)
    try:
        body = _post(
            server,
            "/workbench",
            [*_medicaid_only_fields(), ("action", "save")],
        )
    finally:
        server.shutdown()
        server.server_close()

    assert "Saved case" in body
    assert 'data-saved="' in body
    after = {path.name: path.read_text() for path in sorted(case_dir.glob("*.csv"))}
    assert after == before


def test_case_saved_from_the_page_passes_without_the_app(tmp_path):
    repo = _copy_fixture(tmp_path)
    server = _with_server(repo)
    try:
        body = _post(
            server,
            "/workbench",
            [
                *_medicaid_only_fields(case=None),
                ("case_name", "from_the_app"),
                ("action", "save"),
            ],
        )
    finally:
        server.shutdown()
        server.server_close()

    assert "Saved case" in body
    assert "medicaid_members/from_the_app" in body
    folder = repo / "tests" / "cases" / "medicaid_members" / "from_the_app"
    assert folder.is_dir()
    config = RepositoryConfig.load(repo)
    result = run_case(
        folder, Engine(catalog=config.catalog(), executor=DuckDBExecutor())
    )
    assert result.passed, result.report()
