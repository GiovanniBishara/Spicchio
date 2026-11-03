"""Small guards used wherever Spicchio touches the system.

Spicchio opens files that may come from anywhere (a download, an email
attachment), so it treats every input as untrusted:

* external programs are found by absolute path only, never in the current
  folder (on Windows a planted ``ffmpeg.exe`` next to your files would
  otherwise run instead of the real one);
* nothing is ever passed through a shell;
* outputs never follow a symbolic link or replace an existing file.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _safe_dirs() -> list[Path]:
    """PATH entries that are absolute and are not the current folder."""
    here = Path.cwd().resolve()
    dirs = []
    for raw in os.environ.get("PATH", "").split(os.pathsep):
        if not raw or not os.path.isabs(raw):
            continue  # an empty or relative entry means "the current folder"
        d = Path(raw)
        try:
            if d.resolve() == here:
                continue
        except OSError:
            continue
        dirs.append(d)
    return dirs


def find_program(name: str) -> str | None:
    """Absolute path of ``name`` on PATH, skipping the current folder; None if missing."""
    exts = [""]
    if sys.platform == "win32":
        exts = [e.lower() for e in os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD").split(";") if e]
        exts = [e for e in exts if e in (".exe", ".com")]  # never a .bat/.cmd: those go through cmd.exe
    for d in _safe_dirs():
        for ext in exts:
            candidate = d / (name + ext)
            # exists + not a folder (not is_file): Windows "app execution aliases" like wt.exe count
            if os.path.exists(candidate) and not os.path.isdir(candidate) and os.access(candidate, os.X_OK):
                return str(candidate)
    return None


def windows_program(*parts: str) -> str:
    """A program that ships with Windows, by its full path under %SystemRoot%."""
    root = os.environ.get("SystemRoot", r"C:\Windows")
    return str(Path(root, *parts))


def free(path: Path) -> bool:
    """True if nothing is at ``path``, not even a dangling symbolic link."""
    return not os.path.lexists(path)
