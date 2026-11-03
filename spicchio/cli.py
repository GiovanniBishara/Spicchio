"""Command line: the same actions as the wheel, handy for scripts and for testing.

    spicchio                      start the wheel (tray app)
    spicchio list FILE...         show the slices these files would get
    spicchio run ACTION FILE...   run one action, e.g. `spicchio run img.pdf photo.jpg`
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from spicchio import __version__
from spicchio.actions import ActionError, actions_for, all_actions, get


def _paths(raw: list[str]) -> list[Path]:
    paths = [Path(p).expanduser().resolve() for p in raw]
    missing = [p for p in paths if not p.exists()]
    if missing:
        raise SystemExit("not found: " + ", ".join(str(p) for p in missing))
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="spicchio", description="Drag a file, press Shift, drop it on a slice.")
    parser.add_argument("--version", action="version", version=f"spicchio {__version__}")
    sub = parser.add_subparsers(dest="cmd")
    p_list = sub.add_parser("list", help="show the actions available for the files")
    p_list.add_argument("files", nargs="+")
    p_run = sub.add_parser("run", help="run an action on the files")
    p_run.add_argument("action")
    p_run.add_argument("files", nargs="+")
    sub.add_parser("actions", help="list every action")
    args = parser.parse_args(argv)

    if args.cmd is None:
        from spicchio.app import run_app

        return run_app()
    if args.cmd == "actions":
        for a in all_actions():
            print(f"{a.id:16} {a.label:12} {', '.join(sorted(k.value for k in a.kinds))}")
        return 0
    if args.cmd == "list":
        for a in actions_for(_paths(args.files)):
            print(f"{a.id:16} {a.label}")
        return 0

    paths = _paths(args.files)
    try:
        action = get(args.action)
    except KeyError:
        print(f"unknown action: {args.action} (see `spicchio actions`)", file=sys.stderr)
        return 2
    if not action.applies_to(paths):
        print(f"{action.id} does not apply to these files", file=sys.stderr)
        return 2
    try:
        for out in action(paths):
            print(out)
    except ActionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0
