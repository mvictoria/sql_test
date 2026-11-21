import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from sql_test.integrations.discover import Discovery, discover


def create_server(
    repository: Path, host: str = "127.0.0.1", port: int = 8765
) -> ThreadingHTTPServer:
    repository = repository.resolve()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("app server must bind to localhost only")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path not in {"/", "/index.html"}:
                self.send_error(404)
                return
            body = _page(discover(repository)).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
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


def _page(result: Discovery) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>sql-test</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; }}
    h1 {{ font-size: 1.25rem; }}
    h2 {{ font-size: 1rem; margin-top: 1.5rem; }}
    ul {{ padding-left: 1.25rem; }}
    .empty {{ color: #666; }}
  </style>
</head>
<body>
  <h1>sql-test</h1>
  {_section("Models", result.models)}
  {_section("Sources", result.sources)}
  {_cases_section(result)}
</body>
</html>
"""


def _section(title: str, names: tuple[str, ...]) -> str:
    if not names:
        return f"<h2>{html.escape(title)}</h2><p class='empty'>None</p>"
    items = "".join(f"<li>{html.escape(name)}</li>" for name in names)
    return f"<h2>{html.escape(title)}</h2><ul>{items}</ul>"


def _cases_section(result: Discovery) -> str:
    if not result.cases:
        return "<h2>Cases</h2><p class='empty'>None</p>"
    items = "".join(
        f"<li>{html.escape(case.target)} / {html.escape(case.name)}</li>"
        for case in result.cases
    )
    return f"<h2>Cases</h2><ul>{items}</ul>"
