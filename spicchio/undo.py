"""Undo: move what an action created to the Recycle Bin (Trash on macOS).

Nothing is deleted for good, so an undo can itself be undone from the bin.
Folders created by an action (``report-pages``) go too, once they are empty.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from spicchio.actions import ActionError


def _system_trash(path: Path) -> None:
    try:
        from send2trash import send2trash
    except ImportError as exc:  # pragma: no cover
        raise ActionError("Undo needs the Send2Trash package") from exc
    send2trash(str(path))


def undo(outputs: Sequence[Path], sources: Sequence[Path], trash: Callable[[Path], None] = _system_trash) -> int:
    """Trash ``outputs``; return how many files went. ``sources`` are never touched."""
    keep = {s.resolve() for s in sources}
    keep_dirs = {s.resolve().parent for s in sources}
    moved = 0
    folders: set[Path] = set()
    for out in outputs:
        out = out.resolve()
        if out in keep or not out.exists():
            continue
        trash(out)
        moved += 1
        if out.parent not in keep_dirs:
            folders.add(out.parent)
    for folder in sorted(folders, key=lambda p: len(p.parts), reverse=True):
        if folder.exists() and not any(folder.iterdir()):
            trash(folder)
    return moved
