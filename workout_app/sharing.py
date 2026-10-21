"""Pure helpers for copying data between lightweight user profiles."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable


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


def _exercise_content(exercise: dict[str, Any]) -> dict[str, Any]:
    """Return every exercise field except its profile-specific identifier."""

    return {key: value for key, value in exercise.items() if key != "id"}


def _referenced_exercise_ids(routine: dict[str, Any]) -> list[str]:
    """Return a routine's default and alternate exercise IDs in first-use order."""

    referenced_ids: list[str] = []
    for slot in sorted(routine["slots"], key=lambda item: item["order"]):
        for exercise_id in [
            slot["default_exercise_id"],
            *slot.get("alternative_exercise_ids", []),
        ]:
            if exercise_id not in referenced_ids:
                referenced_ids.append(exercise_id)
    return referenced_ids


def missing_routine_exercises(
    target_document: dict[str, Any],
    source_document: dict[str, Any],
    source_routine: dict[str, Any],
) -> list[dict[str, Any]]:
    """List referenced source exercises without a full-content target match.

    Names alone are deliberately not considered matches. This prevents a
    same-named exercise with different muscles, tags, notes, or URL from being
    silently substituted while importing a routine.
    """

    source_by_id = {
        exercise["id"]: exercise for exercise in source_document["exercises"]
    }
    target_contents = [
        _exercise_content(exercise) for exercise in target_document["exercises"]
    ]
    return [
        deepcopy(source_by_id[exercise_id])
        for exercise_id in _referenced_exercise_ids(source_routine)
        if _exercise_content(source_by_id[exercise_id]) not in target_contents
    ]


def copy_routine_into_documents(
    target_exercise_document: dict[str, Any],
    target_routine_document: dict[str, Any],
    source_exercise_document: dict[str, Any],
    source_routine: dict[str, Any],
    id_factory: Callable[[], str],
) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Copy a routine and its nonmatching exercise dependencies into a profile.

    Fully identical exercises are reused with their target-profile IDs. Every
    other referenced exercise receives a fresh ID, even when its name matches
    an existing exercise. Routine, slot, and superset-group IDs are also
    regenerated so the imported data remains independent of its source.
    """

    updated_exercises = deepcopy(target_exercise_document)
    updated_routines = deepcopy(target_routine_document)
    source_by_id = {
        exercise["id"]: exercise for exercise in source_exercise_document["exercises"]
    }

    exercise_id_map: dict[str, str] = {}
    for source_exercise_id in _referenced_exercise_ids(source_routine):
        source_exercise = source_by_id[source_exercise_id]
        source_content = _exercise_content(source_exercise)
        matching_target = next(
            (
                exercise
                for exercise in updated_exercises["exercises"]
                if _exercise_content(exercise) == source_content
            ),
            None,
        )
        if matching_target is not None:
            exercise_id_map[source_exercise_id] = matching_target["id"]
            continue

        imported_exercise = deepcopy(source_exercise)
        imported_exercise["id"] = id_factory()
        updated_exercises["exercises"].append(imported_exercise)
        exercise_id_map[source_exercise_id] = imported_exercise["id"]

    imported_routine = deepcopy(source_routine)
    imported_routine["id"] = id_factory()
    imported_routine_id = imported_routine["id"]
    group_id_map: dict[str, str] = {}
    for slot in imported_routine["slots"]:
        slot["id"] = id_factory()
        slot["default_exercise_id"] = exercise_id_map[slot["default_exercise_id"]]
        slot["alternative_exercise_ids"] = [
            exercise_id_map[exercise_id]
            for exercise_id in slot.get("alternative_exercise_ids", [])
        ]
        source_group_id = slot.get("superset_group_id")
        if source_group_id is not None:
            if source_group_id not in group_id_map:
                group_id_map[source_group_id] = id_factory()
            slot["superset_group_id"] = group_id_map[source_group_id]

    updated_routines["routines"].append(imported_routine)
    return updated_exercises, updated_routines, imported_routine_id
