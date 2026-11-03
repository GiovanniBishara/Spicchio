"""File kinds and safe output paths.

Spicchio never overwrites anything: every result is written next to the
original, and if the name is taken it becomes ``name (1).ext``, ``name (2).ext``...
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from spicchio.safety import free


class Kind(str, Enum):
    IMAGE = "image"
    PDF = "pdf"
    VIDEO = "video"
    AUDIO = "audio"
    DATA = "data"
    OTHER = "other"


_EXTENSIONS: dict[Kind, set[str]] = {
    Kind.IMAGE: {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff", ".heic", ".heif"},
    Kind.PDF: {".pdf"},
    Kind.VIDEO: {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"},
    Kind.AUDIO: {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac"},
    Kind.DATA: {".csv", ".json"},
}


def kind_of(path: Path) -> Kind:
    """Return the kind of a file from its extension (case-insensitive)."""
    if path.is_dir():
        return Kind.OTHER
    ext = path.suffix.lower()
    for kind, exts in _EXTENSIONS.items():
        if ext in exts:
            return kind
    return Kind.OTHER


def unique_path(path: Path) -> Path:
    """Return ``path`` if it is free, otherwise ``stem (n).suffix`` with the first free n.

    "Free" includes dangling symbolic links: writing through one would create a
    file somewhere else entirely.
    """
    if free(path):
        return path
    n = 1
    while True:
        candidate = path.with_name(f"{path.stem} ({n}){path.suffix}")
        if free(candidate):
            return candidate
        n += 1


def output_path(source: Path, suffix: str, tag: str = "") -> Path:
    """Build a free output path next to ``source``.

    ``suffix`` is the new extension (``".pdf"``); ``tag`` is appended to the
    stem when the extension alone would not tell the files apart
    (``photo.jpg`` -> ``photo-compressed.jpg``).
    """
    stem = f"{source.stem}-{tag}" if tag else source.stem
    return unique_path(source.with_name(stem + suffix))


def output_dir(source: Path, tag: str) -> Path:
    """Create and return a free folder next to ``source`` (``report-pages``)."""
    folder = unique_path(source.with_name(f"{source.stem}-{tag}"))
    folder.mkdir(parents=True)
    return folder
