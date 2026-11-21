import html
from urllib.parse import quote

from sql_test.engine import Catalog
from sql_test.integrations.app.router import Request, Response
from sql_test.integrations.config import RepositoryConfig
from sql_test.integrations.discover import Discovery, discover
from sql_test.testing import case_counts, pipeline_cases, pipeline_counts


def get(request: Request) -> Response | None:
    repository = request.repository
    result = discover(repository)
    catalog = RepositoryConfig.load(repository).catalog()
    table = (request.query.get("pipelines") or [None])[0]
    if table:
        page = _pipelines_page(result, catalog, table)
        if page is None:
            return None
        return Response(body=page)
    return Response(body=_page(result, catalog))


def _page(result: Discovery, catalog: Catalog) -> str:
    tables = (*result.models, *result.sources)
    tests = case_counts(tables, result.cases)
    pipelines = pipeline_counts(tables, result.cases, catalog)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>sql-test</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; }}
    h1 {{ font-size: 1.25rem; }}
    h2 {{ font-size: 1rem; margin-top: 1.5rem; }}
    table.coverage {{ border-collapse: collapse; margin: 0.5rem 0 1rem; }}
    .coverage th, .coverage td {{ border: 1px solid #ccc; padding: 0.35rem 0.6rem; text-align: left; }}
    .coverage th {{ background: #f4f4f4; font-size: 0.85rem; }}
    .coverage td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .coverage a {{ color: inherit; }}
    ul {{ padding-left: 1.25rem; }}
    .empty {{ color: #666; }}
    .kind {{ color: #666; font-size: 0.85rem; }}
  </style>
</head>
<body>
  <h1>sql-test</h1>
  {_tables_section(result, tests, pipelines)}
  {_cases_section(result)}
</body>
</html>
"""


def _tables_section(
    result: Discovery,
    tests: dict[str, int],
    pipelines: dict[str, int],
) -> str:
    models = set(result.models)
    rows = []
    for name in (*result.models, *result.sources):
        kind = "model" if name in models else "source"
        test_n = tests[name]
        pipe_n = pipelines[name]
        pipe_cell = (
            f'<a href="/?pipelines={quote(name, safe="")}" '
            f'data-pipelines="{pipe_n}">{pipe_n}</a>'
            if pipe_n
            else '<span data-pipelines="0">0</span>'
        )
        rows.append(
            "<tr>"
            f'<td><a href="/workbench?target={quote(name, safe="")}" '
            f'data-table="{html.escape(name)}">{html.escape(name)}</a> '
            f'<span class="kind">{kind}</span></td>'
            f'<td class="num" data-tests="{test_n}">{test_n}</td>'
            f'<td class="num">{pipe_cell}</td>'
            "</tr>"
        )
    if not rows:
        return "<h2>Tables</h2><p class='empty'>None</p>"
    return (
        "<h2>Tables</h2>"
        '<table class="coverage">'
        "<thead><tr><th>Table</th><th>Tests</th><th>In pipelines</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
    )


def _pipelines_page(result: Discovery, catalog: Catalog, table: str) -> str | None:
    tables = set(result.models) | set(result.sources)
    if table not in tables:
        return None
    cases = pipeline_cases(table, result.cases, catalog)
    if cases:
        items = "".join(
            (
                f'<li><a href="/workbench?case='
                f'{quote(f"{case.target}/{case.name}", safe="")}" '
                f'data-pipeline-case="{html.escape(case.target)}/{html.escape(case.name)}">'
                f"{html.escape(case.target)} / {html.escape(case.name)}</a></li>"
            )
            for case in cases
        )
        listing = f"<ul>{items}</ul>"
    else:
        listing = "<p class='empty'>None</p>"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>In pipelines — {html.escape(table)}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; }}
    h1 {{ font-size: 1.25rem; }}
    ul {{ padding-left: 1.25rem; }}
    .empty {{ color: #666; }}
  </style>
</head>
<body>
  <p><a href="/">← sql-test</a></p>
  <h1>In pipelines — <code>{html.escape(table)}</code></h1>
  <p>Cases that execute this table without targeting it.</p>
  {listing}
</body>
</html>
"""


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
