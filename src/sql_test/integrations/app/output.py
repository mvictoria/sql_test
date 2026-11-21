import html

from sql_test.engine import RunResult


def output_section(result: RunResult) -> str:
    rows = result.rows
    if not rows:
        return '<h2>Output</h2><p class="empty" data-output-rows="0">No rows</p>'
    columns = list(rows[0].keys())
    headers = "".join(f"<th>{html.escape(name)}</th>" for name in columns)
    body = "".join(
        "<tr>"
        + "".join(
            f"<td>{html.escape('' if row.get(name) is None else str(row.get(name)))}</td>"
            for name in columns
        )
        + "</tr>"
        for row in rows
    )
    return (
        "<h2>Output</h2>"
        f'<table class="output" data-output-rows="{len(rows)}">'
        f"<thead><tr>{headers}</tr></thead>"
        f"<tbody>{body}</tbody>"
        "</table>"
    )
