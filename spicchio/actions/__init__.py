"""All actions. Importing this package registers them in a fixed order:
the order is the order of the slices around the wheel."""

from spicchio.actions import images, pdf, media, data  # noqa: F401  (registration side effects)
from spicchio.actions.base import SIDE_NAMES, SIDES, Action, ActionError, Done, actions_for, all_actions, get, sides_for

__all__ = ["SIDES", "SIDE_NAMES", "Action", "ActionError", "Done", "actions_for", "all_actions", "get", "sides_for"]
