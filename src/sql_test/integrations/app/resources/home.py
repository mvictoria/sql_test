import html
from urllib.parse import quote

from sql_test.integrations.app.router import Request, Response
from sql_test.integrations.discover import Discovery, discover


def get(request: Request) -> Response:
    return Response(body=_page(discover(request.repository)))


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
  {_model_section(result.models)}
  {_section("Sources", result.sources)}
  {_cases_section(result)}
</body>
</html>
"""


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
