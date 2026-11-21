import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from sql_test.engine.catalog.mapping import read_operations
from sql_test.engine.relation import Relation
from sql_test.integrations.discover import MAPPING, SQLS, Discovery, discover


def create_server(
    repository: Path, host: str = "127.0.0.1", port: int = 8765
) -> ThreadingHTTPServer:
    repository = repository.resolve()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("app server must bind to localhost only")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path in {"/", "/index.html"}:
                body = _home(discover(repository)).encode()
            elif parsed.path == "/workbench":
                page = _workbench(
                    repository, discover(repository), parse_qs(parsed.query)
                )
                if page is None:
                    self.send_error(404)
                    return
                body = page.encode()
            else:
                self.send_error(404)
                return
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


def _home(result: Discovery) -> str:
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
  {_model_section(result.models)}
  {_section("Sources", result.sources)}
  {_cases_section(result)}
</body>
</html>
"""


def _workbench(
    repository: Path, result: Discovery, query: dict[str, list[str]]
) -> str | None:
    case_name: str | None = None
    if query.get("case"):
        raw = query["case"][0]
        if "/" not in raw:
            return None
        target, case_name = raw.split("/", 1)
        if not any(c.target == target and c.name == case_name for c in result.cases):
            return None
    elif query.get("target"):
        target = query["target"][0]
        if target not in result.models and target not in result.sources:
            return None
    else:
        return None

    case_line = (
        f"<p>Case: <strong>{html.escape(case_name)}</strong></p>" if case_name else ""
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Workbench — {html.escape(target)}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; }}
    h1 {{ font-size: 1.25rem; }}
    h2 {{ font-size: 1rem; margin-top: 1.5rem; }}
    a {{ color: inherit; }}
    pre {{ background: #f4f4f4; padding: 1rem; overflow: auto; }}
    .empty {{ color: #666; }}
  </style>
</head>
<body>
  <p><a href="/">← sql-test</a></p>
  <h1>Workbench</h1>
  <p>Table under test: <strong>{html.escape(target)}</strong></p>
  {case_line}
  {_sql_section(repository, target)}
</body>
</html>
"""


def _sql_section(repository: Path, target: str) -> str:
    relation = Relation.parse(target)
    operations = [
        operation
        for operation in read_operations(repository / MAPPING, repository / SQLS)
        if operation.writes == relation
    ]
    if not operations:
        return "<h2>SQL</h2><p class='empty'>No producer SQL</p>"
    blocks = "".join(
        (
            f"<h2>{html.escape(operation.sql_file.name)}</h2>"
            f"<pre><code>{html.escape(operation.sql)}</code></pre>"
        )
        for operation in operations
    )
    return blocks


def _model_section(names: tuple[str, ...]) -> str:
    if not names:
        return "<h2>Models</h2><p class='empty'>None</p>"
    items = "".join(
        f'<li><a href="/workbench?target={quote(name, safe="")}">{html.escape(name)}</a></li>'
        for name in names
    )
    return f"<h2>Models</h2><ul>{items}</ul>"


def _section(title: str, names: tuple[str, ...]) -> str:
    if not names:
        return f"<h2>{html.escape(title)}</h2><p class='empty'>None</p>"
    items = "".join(f"<li>{html.escape(name)}</li>" for name in names)
    return f"<h2>{html.escape(title)}</h2><ul>{items}</ul>"


def _cases_section(result: Discovery) -> str:
    if not result.cases:
        return "<h2>Cases</h2><p class='empty'>None</p>"
    items = "".join(
        (
            f'<li><a href="/workbench?case={quote(f"{case.target}/{case.name}", safe="")}">'
            f"{html.escape(case.target)} / {html.escape(case.name)}</a></li>"
        )
        for case in result.cases
    )
    return f"<h2>Cases</h2><ul>{items}</ul>"
