"""Undo: move what an action created to the Recycle Bin (Trash on macOS).

Nothing is deleted for good, so an undo can itself be undone from the bin.
Folders created by an action (``report-pages``) go too, once they are empty.
A file that changed after Spicchio wrote it (you edited it, or something else
took its name) is left alone.
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


Stamp = tuple[int, int, int]


def _stamp(path: Path) -> Stamp | None:
    try:
        st = path.lstat()
    except OSError:
        return None
    return st.st_ino, st.st_size, st.st_mtime_ns


def stamps(outputs: Sequence[Path]) -> dict[Path, Stamp | None]:
    """Remember what each output looks like right after it was written."""
    return {p: _stamp(p) for p in outputs}


def undo(outputs: Sequence[Path], sources: Sequence[Path], trash: Callable[[Path], None] = _system_trash,
         written: dict[Path, Stamp | None] | None = None) -> int:
    """Trash ``outputs``; return how many files went. ``sources`` are never touched.

    With ``written`` (from :func:`stamps`), an output that changed since is kept.
    """
    keep = {s.resolve() for s in sources}
    keep_dirs = {s.resolve().parent for s in sources}
    moved = 0
    folders: set[Path] = set()
    for raw in outputs:
        if raw.is_symlink():
            continue  # Spicchio never creates links: something else put it there
        out = raw.resolve()
        if out in keep or not out.exists():
            continue
        if written is not None and _stamp(raw) != written.get(raw):
            continue
        trash(out)
        moved += 1
        if out.parent not in keep_dirs:
            folders.add(out.parent)
    for folder in sorted(folders, key=lambda p: len(p.parts), reverse=True):
        if folder.exists() and not any(folder.iterdir()):
            trash(folder)
    return moved
