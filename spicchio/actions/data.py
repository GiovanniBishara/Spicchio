"""CSV/JSON conversion and actions that work on any file."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

from spicchio.actions.base import Action, ActionError, Done, each, register
from spicchio.files import Kind, output_path
from spicchio.safety import find_program, windows_program

ANY = frozenset(Kind)
MAX_TEXT_BYTES = 200_000_000  # CSV/JSON are read into memory: refuse absurd sizes up front

# A cell starting with one of these is a formula for Excel and LibreOffice:
# "=HYPERLINK(...)" in someone else's JSON must arrive as text, not run.
_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def _read_text(path: Path) -> str:
    if path.stat().st_size > MAX_TEXT_BYTES:
        raise ActionError(f"{path.name} is too large (over 200 MB)")
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ActionError(f"{path.name} is not UTF-8 text") from exc


def _number(text: str) -> bool:
    try:
        float(text)
        return True
    except ValueError:
        return False


def safe_cell(value):
    """Neutralise spreadsheet formulas: ``=1+1`` becomes ``'=1+1``. Numbers like ``-5`` stay as they are."""
    if isinstance(value, str) and value.startswith(_FORMULA_START) and not _number(value):
        return "'" + value
    return value


def _sniff_dialect(sample: str) -> type[csv.Dialect] | csv.Dialect:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        return csv.excel


def csv_to_json(path: Path) -> Path:
    text = _read_text(path)
    rows = list(csv.DictReader(text.splitlines(), dialect=_sniff_dialect(text[:4096])))
    if not rows:
        raise ActionError(f"{path.name} has no rows")
    out = output_path(path, ".json")
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


def json_to_csv(path: Path) -> Path:
    try:
        data = json.loads(_read_text(path))
    except json.JSONDecodeError as exc:
        raise ActionError(f"{path.name} is not valid JSON (line {exc.lineno})") from exc
    except RecursionError as exc:
        raise ActionError(f"{path.name} is nested too deeply") from exc
    if isinstance(data, dict):
        # {"items": [...]} is common: use the first list of objects we find.
        data = next((v for v in data.values() if isinstance(v, list)), [data])
    if not isinstance(data, list) or not data or not all(isinstance(r, dict) for r in data):
        raise ActionError(f"{path.name} is not a list of objects")
    columns: list[str] = []
    for row in data:
        columns.extend(k for k in row if k not in columns)
    out = output_path(path, ".csv")
    with out.open("w", encoding="utf-8-sig", newline="") as f:  # BOM so Excel opens accents correctly
        writer = csv.DictWriter(f, fieldnames=[safe_cell(c) for c in columns])
        writer.writeheader()
        for row in data:
            writer.writerow({safe_cell(k): safe_cell(json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
                             for k, v in row.items()})
    return out


def zip_files(paths: list[Path]) -> list[Path]:
    name = paths[0].stem if len(paths) == 1 else f"{paths[0].stem}-and-{len(paths) - 1}-more"
    out = output_path(paths[0].with_name(name + ".zip"), ".zip")
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for p in paths:
            if p.is_dir():
                # Links inside a folder are skipped: they could point anywhere on the disk
                # (your SSH keys, say) and would end up in a zip you then send to someone.
                for root, dirs, files in os.walk(p, followlinks=False):
                    dirs.sort()
                    for name in sorted(files):
                        child = Path(root, name)
                        if child.is_symlink() or not child.is_file() or child == out:
                            continue
                        zf.write(child, Path(p.name) / child.relative_to(p))
            else:
                zf.write(p, p.name)
    return [out]


def checksum(path: Path) -> Path:
    if path.is_dir():
        raise ActionError(f"{path.name} is a folder: zip it first")
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    out = output_path(path, ".sha256.txt")
    out.write_text(f"{h.hexdigest()}  {path.name}\n", encoding="utf-8")
    return out


def copy_path(paths: list[Path]) -> Done:
    text = "\n".join(str(p) for p in paths)
    what = "Path copied" if len(paths) == 1 else f"{len(paths)} paths copied"
    return Done(what, text if len(text) < 90 else paths[0].name, clipboard=text)


def terminal_here(paths: list[Path]) -> Done:
    folder = paths[0] if paths[0].is_dir() else paths[0].parent
    # The folder is only ever the working directory or a separate argument, never
    # part of a command line, so a folder name can't smuggle in a command.
    try:
        if sys.platform == "win32":
            if wt := find_program("wt"):
                subprocess.Popen([wt, "-d", str(folder)])
            else:
                shell = windows_program("System32", "WindowsPowerShell", "v1.0", "powershell.exe")
                subprocess.Popen([shell, "-NoExit"], cwd=folder, creationflags=subprocess.CREATE_NEW_CONSOLE)
        elif sys.platform == "darwin":
            subprocess.Popen(["/usr/bin/open", "-a", "Terminal", str(folder)])
        elif term := find_program("x-terminal-emulator"):
            subprocess.Popen([term], cwd=folder)
        else:
            raise ActionError("No terminal found on this system")
    except OSError as exc:
        raise ActionError("Can't open a terminal on this system") from exc
    return Done("Terminal opened", str(folder))


DATA = frozenset({Kind.DATA})
register(Action("data.json", "JSON", DATA, each(csv_to_json), skip_ext=frozenset({".json"}), title="Convert to JSON"))
register(Action("data.csv", "CSV", DATA, each(json_to_csv), skip_ext=frozenset({".csv"}), title="Convert to CSV"))
register(Action("any.zip", "ZIP", ANY, zip_files, mode="many", title="Zip it", side="actions"))
register(Action("any.path", "Copy path", ANY, copy_path, mode="many", title="Copy the full path", side="actions"))
register(Action("any.terminal", "Terminal", ANY, terminal_here, mode="many", title="Open a terminal here", side="actions"))
register(Action("any.sha256", "SHA-256", ANY, each(checksum), title="SHA-256 checksum", side="actions"))
