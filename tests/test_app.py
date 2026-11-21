import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote

from sql_test.integrations.app import create_server

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
    assert 'class="node mocked"' in mocked
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
    assert both.count('class="node mocked"') == 1
    assert "raw_claims" not in both
    assert "Blocked" in body
    assert "raw_members" in body


def test_covering_needs_rows_marks_ready_to_run():
    server = _with_server(DEMO)
    try:
        body = _get(
            server,
            "/workbench?target=customer_summary&mock=staged_claims&mock=raw_members",
        )
    finally:
        server.shutdown()
        server.server_close()

    assert "Ready to run" in body
    assert "Blocked" not in body


def test_selecting_a_case_opens_the_workbench(tmp_path):
    case = tmp_path / "cases" / "medicaid_members" / "alice"
    case.mkdir(parents=True)
    (case / "members.csv").write_text("member_id\n1\n")
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
