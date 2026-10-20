"""In-memory upgrades for older workout data documents."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


# Version 1 stored muscle groups and general descriptors together in ``tags``.
# These established descriptors are the only values we can classify reliably;
# all other values are treated as muscles during the legacy migration.
LEGACY_GENERAL_TAGS = {"push", "pull", "legs", "compound", "isolation"}


def _split_legacy_tags(tags: Any) -> tuple[list[str], list[str]]:
    """Split a legacy mixed tag list without discarding unfamiliar values."""

    if not isinstance(tags, list):
        return [], []
    general = [
        tag
        for tag in tags
        if isinstance(tag, str) and tag.casefold() in LEGACY_GENERAL_TAGS
    ]
    muscles = [
        tag
        for tag in tags
        if isinstance(tag, str) and tag.casefold() not in LEGACY_GENERAL_TAGS
    ]
    if not muscles:
        muscles = list(general)
        general = []
    return muscles, general


def migrate_documents(
    exercise_document: dict[str, Any], routine_document: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return current-shape copies of current or legacy documents."""

    exercises = deepcopy(exercise_document)
    routines = deepcopy(routine_document)

    if isinstance(exercises.get("exercises"), list):
        for exercise in exercises["exercises"]:
            if not isinstance(exercise, dict) or "muscles_targeted" in exercise:
                continue
            muscles, tags = _split_legacy_tags(exercise.get("tags"))
            exercise["muscles_targeted"] = muscles
            exercise["tags"] = tags

    if isinstance(routines.get("routines"), list):
        for routine in routines["routines"]:
            if not isinstance(routine, dict) or not isinstance(routine.get("slots"), list):
                continue
            for slot in routine["slots"]:
                if not isinstance(slot, dict) or "required_muscles" in slot:
                    continue
                muscles, tags = _split_legacy_tags(slot.get("required_tags"))
                slot["required_muscles"] = muscles
                slot["required_tags"] = tags

    return exercises, routines
