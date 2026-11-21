import threading
from http.client import HTTPConnection
from pathlib import Path

from sql_test.integrations.app import create_server

FIXTURE = Path(__file__).parent / "fixtures" / "repos" / "lakehouse-data-customer"


def test_app_page_lists_models_and_sources():
    server = create_server(FIXTURE, host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        assert isinstance(host, str)
        assert isinstance(port, int)
        connection = HTTPConnection(host, port, timeout=5)
        connection.request("GET", "/")
        body = connection.getresponse().read().decode()
        connection.close()
    finally:
        server.shutdown()
        server.server_close()

    assert "medicaid_members" in body
    assert "medicaid_members_named_alice" in body
    assert "members" in body
    assert "Sources" in body
    assert "Boundaries" not in body
