"""The action model and the registry that decides which slices to show.

Actions are grouped in *sides* of the wheel: Convert, Tools and Actions. Shift
opens the first side that has something for the dropped files; tapping Shift
again (or Tab, or the mouse wheel) turns to the next one.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from spicchio.files import Kind, kind_of

SIDES = ("convert", "tools", "actions")
SIDE_NAMES = {"convert": "Convert", "tools": "Tools", "actions": "Actions"}


class ActionError(Exception):
    """A user-facing error: the message is shown as is in the notification."""


@dataclass
class Done:
    """Returned by actions that don't create files (copy a path, open a terminal...)."""

    message: str
    detail: str = ""
    clipboard: str | None = None


class Saved(list):
    """The files an action created, plus an optional note for the notification."""

    def __init__(self, paths=(), note: str = "") -> None:
        super().__init__(paths)
        self.note = note


Result = list[Path] | Done
# An action receives the dropped files and returns the files it created (or a Done).
Runner = Callable[[Sequence[Path]], Result]


@dataclass(frozen=True)
class Action:
    id: str
    label: str
    kinds: frozenset[Kind]
    run: Runner
    # "each": the action works on every file on its own (convert 3 images = 3 outputs).
    # "many": the action needs all files together (merge PDFs, zip).
    mode: str = "each"
    min_files: int = 1
    # Hide the action when the files already have one of these extensions (no "PNG" for a .png).
    skip_ext: frozenset[str] = field(default_factory=frozenset)
    # An optional check, e.g. "is ffmpeg installed?".
    available: Callable[[], bool] = lambda: True
    # Longer description shown in the middle of the wheel ("Convert to PDF"). Defaults to the label.
    title: str = ""
    side: str = "convert"

    @property
    def headline(self) -> str:
        return self.title or self.label

    def applies_to(self, paths: Sequence[Path]) -> bool:
        if len(paths) < self.min_files or not self.available():
            return False
        if not all(kind_of(p) in self.kinds for p in paths):
            return False
        # no "PNG" slice when every file is already a PNG
        return not (self.skip_ext and all(p.suffix.lower() in self.skip_ext for p in paths))

    def __call__(self, paths: Sequence[Path]) -> Result:
        if self.mode == "many":
            return self.run(list(paths))
        out: list[Path] = []
        for p in paths:
            result = self.run([p])
            if isinstance(result, Done):
                return result
            out.extend(result)
        return out


_REGISTRY: list[Action] = []


def register(action: Action) -> Action:
    if any(a.id == action.id for a in _REGISTRY):
        raise ValueError(f"duplicate action id: {action.id}")
    if action.side not in SIDES:
        raise ValueError(f"unknown side for {action.id}: {action.side}")
    _REGISTRY.append(action)
    return action


def all_actions() -> list[Action]:
    return list(_REGISTRY)


def actions_for(paths: Sequence[Path], side: str | None = None, limit: int = 8) -> list[Action]:
    """The actions that make sense for these files, in registry order.

    With ``side`` only that side of the wheel, at most ``limit`` slices.
    """
    if not paths:
        return []
    found = [a for a in _REGISTRY if a.applies_to(paths) and (side is None or a.side == side)]
    return found[:limit] if side else found


def sides_for(paths: Sequence[Path], limit: int = 8) -> list[tuple[str, list[Action]]]:
    """The non-empty sides of the wheel for these files, in order."""
    out = []
    for side in SIDES:
        acts = actions_for(paths, side, limit)
        if acts:
            out.append((side, acts))
    return out


def get(action_id: str) -> Action:
    for a in _REGISTRY:
        if a.id == action_id:
            return a
    raise KeyError(action_id)


def each(fn: Callable[[Path], Path | list[Path]]) -> Runner:
    """Adapt a one-file function to the Runner signature."""

    def run(paths: Sequence[Path]) -> list[Path]:
        result = fn(paths[0])
        return result if isinstance(result, list) else [result]

    return run
