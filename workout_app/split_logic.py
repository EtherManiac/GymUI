"""Pure transformations for a profile's repeating workout split."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def empty_split_document() -> dict[str, Any]:
    """Return a disabled workout split."""

    return {"schema_version": 1, "routine_ids": [], "current_index": 0}


def current_split_routine_id(split_document: dict[str, Any]) -> str | None:
    """Return the routine due next, or None when no split is configured."""

    routine_ids = split_document["routine_ids"]
    if not routine_ids:
        return None
    return routine_ids[split_document["current_index"]]


def advance_split(
    split_document: dict[str, Any], completed_routine_id: str
) -> tuple[dict[str, Any], bool]:
    """Re-anchor the cycle after any completed routine present in the split."""

    updated = deepcopy(split_document)
    routine_ids = updated["routine_ids"]
    if completed_routine_id not in routine_ids:
        return updated, False

    # When a routine occurs more than once, use the first matching occurrence
    # at or after the slot currently due, wrapping around the cycle if needed.
    current_index = updated["current_index"]
    completed_index = next(
        index % len(routine_ids)
        for index in range(current_index, current_index + len(routine_ids))
        if routine_ids[index % len(routine_ids)] == completed_routine_id
    )
    updated["current_index"] = (completed_index + 1) % len(routine_ids)
    return updated, True


def without_routine(
    split_document: dict[str, Any], routine_id: str
) -> dict[str, Any]:
    """Remove every occurrence of a deleted routine while preserving position."""

    current_id = current_split_routine_id(split_document)
    updated = deepcopy(split_document)
    updated["routine_ids"] = [
        saved_id for saved_id in updated["routine_ids"] if saved_id != routine_id
    ]
    if not updated["routine_ids"]:
        updated["current_index"] = 0
    elif current_id in updated["routine_ids"]:
        updated["current_index"] = updated["routine_ids"].index(current_id)
    else:
        updated["current_index"] %= len(updated["routine_ids"])
    return updated
