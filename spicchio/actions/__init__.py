"""All actions. Importing this package registers them in a fixed order:
the order is the order of the slices around the wheel."""

from spicchio.actions import images, pdf, media, data  # noqa: F401  (registration side effects)
from spicchio.actions.base import Action, ActionError, actions_for, all_actions, get

__all__ = ["Action", "ActionError", "actions_for", "all_actions", "get"]
