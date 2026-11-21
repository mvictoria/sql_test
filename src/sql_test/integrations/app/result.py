import html
from pathlib import Path

from sql_test.engine import RunResult
from sql_test.integrations.app.compare_view import compare_section
from sql_test.integrations.app.output import output_section

RESULT_VIEWS = frozenset({"output", "diff"})
DEFAULT_RESULT_VIEW = "output"


def result_section(
    repository: Path,
    target: str,
    expected_rows: list[dict[str, str]],
    run_result: RunResult,
    result_view: str,
) -> str:
    if result_view not in RESULT_VIEWS:
        result_view = DEFAULT_RESULT_VIEW
    output = output_section(run_result)
    diff = compare_section(repository, target, expected_rows, run_result.rows)
    if not diff:
        diff = '<p class="empty">Add expected rows to see a diff</p>'
    return (
        f'<section class="result" data-result-view="{html.escape(result_view)}">'
        f"{_result_nav(result_view)}"
        f'<div class="result-panel" data-panel="output"'
        f"{' hidden' if result_view != 'output' else ''}>{output}</div>"
        f'<div class="result-panel" data-panel="diff"'
        f"{' hidden' if result_view != 'diff' else ''}>{diff}</div>"
        "</section>"
        f"{_toggle_script()}"
    )


def _result_nav(current: str) -> str:
    links = []
    for name, label in (("output", "Output"), ("diff", "Diff")):
        cls = ' class="current"' if name == current else ""
        links.append(
            f'<button type="button" data-result="{html.escape(name)}"{cls}>'
            f"{html.escape(label)}</button>"
        )
    return f'<nav class="result-views">{"".join(links)}</nav>'


def _toggle_script() -> str:
    return """<script>
(() => {
  const root = document.querySelector("section.result");
  if (!root) return;
  const buttons = root.querySelectorAll("nav.result-views button");
  const panels = root.querySelectorAll("[data-panel]");
  const syncForm = (view) => {
    for (const input of document.querySelectorAll('input[name="result_view"]')) {
      input.value = view;
    }
  };
  for (const button of buttons) {
    button.addEventListener("click", () => {
      const view = button.getAttribute("data-result");
      root.setAttribute("data-result-view", view);
      for (const other of buttons) {
        other.classList.toggle("current", other === button);
      }
      for (const panel of panels) {
        panel.hidden = panel.getAttribute("data-panel") !== view;
      }
      syncForm(view);
    });
  }
})();
</script>"""
