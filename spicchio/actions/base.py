"""The action model and the registry that decides which slices to show."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from spicchio.files import Kind, kind_of


class ActionError(Exception):
    """A user-facing error: the message is shown as is in the notification."""


# An action receives the dropped files and returns the files it created.
Runner = Callable[[Sequence[Path]], list[Path]]


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

    @property
    def headline(self) -> str:
        return self.title or self.label

    def applies_to(self, paths: Sequence[Path]) -> bool:
        if len(paths) < self.min_files or not self.available():
            return False
        if not all(kind_of(p) in self.kinds for p in paths):
            return False
        if self.skip_ext and all(p.suffix.lower() in self.skip_ext for p in paths):
            return False
        return True

    def __call__(self, paths: Sequence[Path]) -> list[Path]:
        if self.mode == "many":
            return self.run(list(paths))
        out: list[Path] = []
        for p in paths:
            out.extend(self.run([p]))
        return out


_REGISTRY: list[Action] = []


def register(action: Action) -> Action:
    if any(a.id == action.id for a in _REGISTRY):
        raise ValueError(f"duplicate action id: {action.id}")
    _REGISTRY.append(action)
    return action


def all_actions() -> list[Action]:
    return list(_REGISTRY)


def actions_for(paths: Sequence[Path], limit: int = 8) -> list[Action]:
    """The actions that make sense for these files, in registry order, at most ``limit``."""
    if not paths:
        return []
    return [a for a in _REGISTRY if a.applies_to(paths)][:limit]


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
