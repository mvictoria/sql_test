import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote

from sql_test.integrations.app import create_server

FIXTURE = Path(__file__).parent / "fixtures" / "repos" / "lakehouse-data-customer"


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
    finally:
        server.shutdown()
        server.server_close()

    assert "Workbench" in body
    assert "medicaid_members_named_alice" in body
    assert "table under test" in body.lower()


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
