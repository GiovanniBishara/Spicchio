"""CSV/JSON conversion and actions that work on any file."""

from __future__ import annotations

import csv
import hashlib
import json
import zipfile
from pathlib import Path

from spicchio.actions.base import Action, ActionError, each, register
from spicchio.files import Kind, output_path

ANY = frozenset(Kind)


def _sniff_dialect(sample: str) -> type[csv.Dialect] | csv.Dialect:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        return csv.excel


def csv_to_json(path: Path) -> Path:
    text = path.read_text(encoding="utf-8-sig")
    rows = list(csv.DictReader(text.splitlines(), dialect=_sniff_dialect(text[:4096])))
    if not rows:
        raise ActionError(f"{path.name} has no rows")
    out = output_path(path, ".json")
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


def json_to_csv(path: Path) -> Path:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ActionError(f"{path.name} is not valid JSON (line {exc.lineno})") from exc
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
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in data:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                             for k, v in row.items()})
    return out


def zip_files(paths: list[Path]) -> list[Path]:
    name = paths[0].stem if len(paths) == 1 else f"{paths[0].stem}-and-{len(paths) - 1}-more"
    out = output_path(paths[0].with_name(name + ".zip"), ".zip")
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for p in paths:
            if p.is_dir():
                for child in sorted(p.rglob("*")):
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


register(Action("data.json", "JSON", frozenset({Kind.DATA}), each(csv_to_json), skip_ext=frozenset({".json"}), title="Convert to JSON"))
register(Action("data.csv", "CSV", frozenset({Kind.DATA}), each(json_to_csv), skip_ext=frozenset({".csv"}), title="Convert to CSV"))
register(Action("any.zip", "ZIP", ANY, zip_files, mode="many", title="Zip it"))
register(Action("any.sha256", "SHA-256", ANY, each(checksum), title="SHA-256 checksum"))
