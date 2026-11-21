from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from sql_test.integrations.app.pages import error_page
from sql_test.integrations.app.resources import home, workbench
from sql_test.integrations.app.router import Request, Response, Router


def build_router() -> Router:
    router = Router()
    router.add("GET", "/", home.get)
    router.add("GET", "/workbench", workbench.get)
    router.add("POST", "/workbench", workbench.post)
    return router


def create_server(
    repository: Path, host: str = "127.0.0.1", port: int = 8765
) -> ThreadingHTTPServer:
    repository = repository.resolve()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("app server must bind to localhost only")
    router = build_router()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self._dispatch("GET")

        def do_POST(self) -> None:
            self._dispatch("POST")

        def _dispatch(self, method: str) -> None:
            parsed = urlparse(self.path)
            if method == "POST":
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length).decode()
                query = parse_qs(raw)
            else:
                query = parse_qs(parsed.query)
            request = Request(
                method=method,
                path=parsed.path,
                query=query,
                repository=repository,
            )
            try:
                response = router.dispatch(request)
            except Exception as error:  # noqa: BLE001 — always answer the browser
                self._send(Response(body=error_page(error), status=500))
                return
            if response is None:
                self.send_error(404)
                return
            self._send(response)

        def _send(self, response: Response) -> None:
            body = response.body.encode()
            self.send_response(response.status)
            self.send_header("Content-Type", response.content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    return ThreadingHTTPServer((host, port), Handler)


def serve(repository: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    server = create_server(repository, host=host, port=port)
    bound_host, bound_port = server.server_address[:2]
    assert isinstance(bound_host, str)
    assert isinstance(bound_port, int)
    print(f"sql-test app serving {repository} at http://{bound_host}:{bound_port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()
