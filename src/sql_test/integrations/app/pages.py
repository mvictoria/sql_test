import html


def error_page(error: BaseException) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>sql-test error</title></head>
<body>
  <h1>Something went wrong</h1>
  <p>{html.escape(str(error))}</p>
  <p><a href="/">← sql-test</a></p>
</body>
</html>
"""
