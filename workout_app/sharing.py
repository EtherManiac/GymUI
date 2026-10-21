"""Pure helpers for copying data between lightweight user profiles."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def copy_exercise_into_document(
    target_document: dict[str, Any],
    source_exercise: dict[str, Any],
    new_exercise_id: str,
) -> dict[str, Any]:
    """Return a target document containing an independent exercise copy."""

    updated_document = deepcopy(target_document)
    imported_exercise = deepcopy(source_exercise)
    imported_exercise["id"] = new_exercise_id
    updated_document["exercises"].append(imported_exercise)
    return updated_document

