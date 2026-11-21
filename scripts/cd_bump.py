"""Compute the next release tag from a PR title and the latest git version tag.

PR titles opt into a release with exactly one of: (major), (minor), (patch).
The tag is always applied to main's tip after the PR lands (linear history).
"""

from __future__ import annotations

import argparse
import re
import sys

BUMP_TOKEN = re.compile(r"\((major|minor|patch)\)")


def bump_from_title(title: str) -> str | None:
    found = BUMP_TOKEN.findall(title)
    if not found:
        return None
    if len(set(found)) > 1:
        raise ValueError(f"PR title has conflicting bump tokens: {found}")
    return found[0]


def next_tag(latest: str | None, bump: str) -> str:
    if bump not in {"major", "minor", "patch"}:
        raise ValueError(f"unknown bump: {bump}")
    if latest in (None, ""):
        major, minor, patch = 0, 0, 0
    else:
        body = latest.removeprefix("v")
        major, minor, patch = (int(p) for p in body.split("."))
    if bump == "major":
        major, minor, patch = major + 1, 0, 0
    elif bump == "minor":
        minor, patch = minor + 1, 0
    else:
        patch += 1
    return f"v{major}.{minor}.{patch}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cd_bump")
    sub = parser.add_subparsers(dest="cmd", required=True)

    from_title = sub.add_parser("from-title", help="print bump kind or empty")
    from_title.add_argument("title")

    nxt = sub.add_parser("next", help="print next vX.Y.Z tag")
    nxt.add_argument("latest", nargs="?", default="")
    nxt.add_argument("bump")

    args = parser.parse_args(argv)
    if args.cmd == "from-title":
        bump = bump_from_title(args.title)
        if bump:
            print(bump)
        return 0
    print(next_tag(args.latest or None, args.bump))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(2) from exc
